from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from seller_data_pipeline.ingestion.ads_table_mapping import (
    ADS_TARGET_TABLE_SPECS,
    AdsTargetTableSpec,
    dataclass_to_json_dict,
    get_ads_target_table_spec,
    map_ads_record_to_table_row,
    write_jsonl,
)
from seller_data_pipeline.parsers.amazon.ads_report_parser import AdsReportParser
from seller_data_pipeline.sampling.report_analyzer import analyze_report_file
from seller_data_pipeline.sampling.schema_drift import (
    SchemaValidationResult,
    build_ads_expected_schema,
    validate_report_schema,
)

BLOCKING_SCHEMA_STATUSES = {
    "missing_fields",
    "new_fields",
    "schema_drift",
    "unmapped_fields",
    "validation_failed",
    "empty_report_unexpected",
}


@dataclass(frozen=True)
class AdsPreparedReportResult:
    report_type_id: str
    target_table: str | None
    raw_file_path: str | None
    schema_validation_status: str | None
    requires_review: bool
    skipped: bool
    skip_reason: str | None
    parsed_row_count: int
    prepared_row_count: int
    preview_file_path: str | None
    schema_validation_event: dict[str, Any] | None


@dataclass(frozen=True)
class AdsIngestionDryRunResult:
    workflow_name: str
    profile_id: str
    marketplace_id: str | None
    started_at: str
    finished_at: str
    status: str
    requires_review: bool
    processed_file_count: int
    parsed_row_count: int
    prepared_row_count: int
    preview_file_count: int
    skipped_report_count: int
    output_dir: str
    report_results: tuple[AdsPreparedReportResult, ...]
    task_audit_event: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(asdict(self), ensure_ascii=False, default=str))


class AdsIngestionDryRunService:
    """Prepare Amazon Ads DB-ready rows locally without touching Azure SQL.

    This service is the guardrail between raw reports and future repository/upsert code. It stores
    preview rows, schema-validation events and a task-audit event so table mapping can be reviewed
    before executing database migrations or real writes.
    """

    def __init__(
        self,
        *,
        raw_reports_root: str | Path,
        output_root: str | Path = "runtime/ingestion/amazon_ads",
    ) -> None:
        self.raw_reports_root = Path(raw_reports_root)
        self.output_root = Path(output_root)
        self.parser = AdsReportParser()

    def prepare(
        self,
        *,
        profile_id: str,
        report_type_ids: list[str] | None = None,
        marketplace_id: str | None = None,
        fail_on_review: bool = False,
    ) -> AdsIngestionDryRunResult:
        started_at = _utc_now_iso()
        report_type_ids = report_type_ids or [
            spec.report_type_id for spec in ADS_TARGET_TABLE_SPECS if spec.table_ready
        ]
        run_output_dir = self._build_run_output_dir(profile_id=profile_id)
        preview_dir = run_output_dir / "previews"
        schema_events_path = run_output_dir / "schema_validation_events.jsonl"
        results: list[AdsPreparedReportResult] = []
        schema_events: list[dict[str, Any]] = []

        for report_type_id in report_type_ids:
            prepared = self._prepare_one_report(
                profile_id=profile_id,
                report_type_id=report_type_id,
                marketplace_id=marketplace_id,
                preview_dir=preview_dir,
            )
            results.append(prepared)
            if prepared.schema_validation_event is not None:
                schema_events.append(prepared.schema_validation_event)

        write_jsonl(schema_events_path, schema_events)
        finished_at = _utc_now_iso()
        requires_review = any(result.requires_review for result in results)
        status = "requires_review" if requires_review else "success"
        if fail_on_review and requires_review:
            status = "failed_requires_review"
        task_audit_event = build_task_audit_event(
            profile_id=profile_id,
            marketplace_id=marketplace_id,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            output_dir=str(run_output_dir),
            report_results=results,
        )
        result = AdsIngestionDryRunResult(
            workflow_name="amazon_ads_ingestion_dry_run",
            profile_id=profile_id,
            marketplace_id=marketplace_id,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            requires_review=requires_review,
            processed_file_count=sum(1 for item in results if item.raw_file_path),
            parsed_row_count=sum(item.parsed_row_count for item in results),
            prepared_row_count=sum(item.prepared_row_count for item in results),
            preview_file_count=sum(1 for item in results if item.preview_file_path),
            skipped_report_count=sum(1 for item in results if item.skipped),
            output_dir=str(run_output_dir),
            report_results=tuple(results),
            task_audit_event=task_audit_event,
        )
        _write_json(run_output_dir / "task_audit_event.json", task_audit_event)
        _write_json(run_output_dir / "ads_ingestion_summary.json", result.to_dict())
        return result

    def _prepare_one_report(
        self,
        *,
        profile_id: str,
        report_type_id: str,
        marketplace_id: str | None,
        preview_dir: Path,
    ) -> AdsPreparedReportResult:
        table_spec = get_ads_target_table_spec(report_type_id)
        if table_spec is None:
            return AdsPreparedReportResult(
                report_type_id=report_type_id,
                target_table=None,
                raw_file_path=None,
                schema_validation_status=None,
                requires_review=True,
                skipped=True,
                skip_reason="no_target_table_spec",
                parsed_row_count=0,
                prepared_row_count=0,
                preview_file_path=None,
                schema_validation_event=None,
            )
        if not table_spec.table_ready:
            return AdsPreparedReportResult(
                report_type_id=report_type_id,
                target_table=table_spec.target_table,
                raw_file_path=None,
                schema_validation_status=None,
                requires_review=False,
                skipped=True,
                skip_reason="target_table_not_ready_non_empty_sample_required",
                parsed_row_count=0,
                prepared_row_count=0,
                preview_file_path=None,
                schema_validation_event=None,
            )

        raw_file_path = find_latest_ads_raw_file(
            raw_reports_root=self.raw_reports_root,
            profile_id=profile_id,
            report_type_id=report_type_id,
        )
        if raw_file_path is None:
            return AdsPreparedReportResult(
                report_type_id=report_type_id,
                target_table=table_spec.target_table,
                raw_file_path=None,
                schema_validation_status=None,
                requires_review=True,
                skipped=True,
                skip_reason="raw_file_not_found",
                parsed_row_count=0,
                prepared_row_count=0,
                preview_file_path=None,
                schema_validation_event=None,
            )

        analysis = analyze_report_file(
            raw_file_path=str(raw_file_path),
            report_type=report_type_id,
            marketplace_id=profile_id,
            source_system="amazon_ads",
            redact_sample_values=True,
        )
        schema_result = validate_report_schema(
            analysis=analysis,
            expected_schema=build_ads_expected_schema(report_type_id),
        )
        schema_event = build_schema_validation_event_row(schema_result)
        if schema_result.status in BLOCKING_SCHEMA_STATUSES or schema_result.requires_review:
            return AdsPreparedReportResult(
                report_type_id=report_type_id,
                target_table=table_spec.target_table,
                raw_file_path=str(raw_file_path),
                schema_validation_status=schema_result.status,
                requires_review=True,
                skipped=True,
                skip_reason="schema_validation_requires_review",
                parsed_row_count=0,
                prepared_row_count=0,
                preview_file_path=None,
                schema_validation_event=schema_event,
            )

        records = self.parser.parse_file(
            raw_file_path=raw_file_path,
            profile_id=profile_id,
            report_type_id=report_type_id,
            source_report_id=raw_file_path.stem,
        )
        rows = [
            map_ads_record_to_table_row(
                record=record,
                table_spec=table_spec,
                marketplace_id=marketplace_id,
            )
            for record in records
        ]
        preview_path = preview_dir / f"{table_spec.target_table}.preview.jsonl"
        write_jsonl(preview_path, rows)
        return AdsPreparedReportResult(
            report_type_id=report_type_id,
            target_table=table_spec.target_table,
            raw_file_path=str(raw_file_path),
            schema_validation_status=schema_result.status,
            requires_review=False,
            skipped=False,
            skip_reason=None,
            parsed_row_count=len(records),
            prepared_row_count=len(rows),
            preview_file_path=str(preview_path),
            schema_validation_event=schema_event,
        )

    def _build_run_output_dir(self, *, profile_id: str) -> Path:
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        output_dir = self.output_root / _safe_path_part(profile_id) / timestamp
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir


def find_latest_ads_raw_file(
    *,
    raw_reports_root: str | Path,
    profile_id: str,
    report_type_id: str,
) -> Path | None:
    root = Path(raw_reports_root) / "amazon_ads" / str(profile_id) / str(report_type_id)
    if not root.exists():
        return None
    candidates = [path for path in root.rglob("*.json") if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def build_schema_validation_event_row(result: SchemaValidationResult) -> dict[str, Any]:
    notification_status = "pending" if result.requires_review else "not_required"
    return {
        "source_system": result.source_system,
        "marketplace_id": result.marketplace_id,
        "report_type": result.report_type,
        "report_id": Path(result.raw_file_path).stem if result.raw_file_path else None,
        "raw_file_id": None,
        "raw_file_path": result.raw_file_path,
        "validation_stage": "pre_ingestion_dry_run",
        "validation_status": result.status,
        "severity": result.severity,
        "row_count": result.row_count,
        "observed_fields_json": json.dumps(list(result.observed_fields), ensure_ascii=False),
        "expected_fields_json": json.dumps(list(result.expected_fields), ensure_ascii=False),
        "missing_fields_json": json.dumps(list(result.missing_fields), ensure_ascii=False),
        "new_fields_json": json.dumps(list(result.new_fields), ensure_ascii=False),
        "unmapped_fields_json": json.dumps(list(result.unmapped_fields), ensure_ascii=False),
        "requires_review": result.requires_review,
        "notification_status": notification_status,
        "notified_at": None,
        "message": result.message,
        "source_run_id": None,
    }


def build_task_audit_event(
    *,
    profile_id: str,
    marketplace_id: str | None,
    started_at: str,
    finished_at: str,
    status: str,
    output_dir: str,
    report_results: list[AdsPreparedReportResult],
) -> dict[str, Any]:
    rows_read = sum(item.parsed_row_count for item in report_results)
    rows_written = sum(item.prepared_row_count for item in report_results)
    rows_skipped = sum(1 for item in report_results if item.skipped)
    files_created = sum(1 for item in report_results if item.preview_file_path) + 3
    return {
        "workflow_name": "amazon_ads_ingestion_dry_run",
        "job_name": "prepare_ads_ingestion",
        "task_type": "ingestion_dry_run",
        "trigger_type": "manual",
        "run_mode": "local_dry_run",
        "parent_run_id": None,
        "job_execution_id": Path(output_dir).name,
        "marketplace_id": marketplace_id,
        "source_system": "amazon_ads",
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": _duration_ms(started_at, finished_at),
        "date_start": None,
        "date_end": None,
        "rows_read": rows_read,
        "rows_written": rows_written,
        "rows_skipped": rows_skipped,
        "rows_failed": 0,
        "files_created": files_created,
        "retry_count": 0,
        "config_snapshot_json": json.dumps(
            {
                "profile_id": profile_id,
                "marketplace_id": marketplace_id,
                "output_dir": output_dir,
                "report_type_ids": [item.report_type_id for item in report_results],
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        "message": _build_task_message(report_results),
        "error_type": None,
        "error_detail": None,
    }


def _build_task_message(report_results: list[AdsPreparedReportResult]) -> str:
    requires_review = [item.report_type_id for item in report_results if item.requires_review]
    if requires_review:
        return "Requires review: " + ", ".join(requires_review)
    prepared = [
        f"{item.report_type_id}={item.prepared_row_count}"
        for item in report_results
        if not item.skipped
    ]
    return "Prepared Ads DB-ready preview rows: " + ", ".join(prepared)


def _duration_ms(started_at: str, finished_at: str) -> int:
    start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    finish = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
    return int((finish - start).total_seconds() * 1000)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _write_json(path: str | Path, payload: dict[str, Any]) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _safe_path_part(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value)
    return safe[:120] or "unknown"


__all__ = [
    "AdsIngestionDryRunResult",
    "AdsIngestionDryRunService",
    "AdsPreparedReportResult",
    "BLOCKING_SCHEMA_STATUSES",
    "build_schema_validation_event_row",
    "build_task_audit_event",
    "find_latest_ads_raw_file",
]
