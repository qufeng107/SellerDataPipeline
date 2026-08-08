from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from seller_data_pipeline.ingestion.ads_ingestion_dry_run import (
    build_schema_validation_event_row,
)
from seller_data_pipeline.ingestion.listing_table_mapping import (
    LISTING_REPORT_TYPE,
    LISTING_TARGET_TABLE_SPEC,
    map_listing_record_to_table_row,
    write_jsonl,
)
from seller_data_pipeline.parsers.amazon.listings_all_data_parser import ListingsAllDataParser
from seller_data_pipeline.sampling.report_analyzer import analyze_report_file
from seller_data_pipeline.sampling.schema_drift import (
    BLOCKING_SCHEMA_STATUSES,
    ExpectedReportSchema,
    validate_report_schema,
)


@dataclass(frozen=True)
class ListingPreparedReportResult:
    report_type: str
    target_table: str
    raw_file_path: str | None
    snapshot_date: str | None
    schema_validation_status: str | None
    requires_review: bool
    skipped: bool
    skip_reason: str | None
    parsed_row_count: int
    prepared_row_count: int
    preview_file_path: str | None
    schema_validation_event: dict[str, Any] | None


@dataclass(frozen=True)
class ListingIngestionDryRunResult:
    workflow_name: str
    marketplace_id: str
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
    report_result: ListingPreparedReportResult
    task_audit_event: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(asdict(self), ensure_ascii=False, default=str))


class ListingIngestionDryRunService:
    """Prepare DB-ready listing snapshot rows locally without touching Azure SQL."""

    def __init__(
        self,
        *,
        raw_reports_root: str | Path,
        output_root: str | Path = "runtime/ingestion/sp_api",
    ) -> None:
        self.raw_reports_root = Path(raw_reports_root)
        self.output_root = Path(output_root)
        self.parser = ListingsAllDataParser()

    def prepare(
        self,
        *,
        marketplace_id: str,
        raw_file_path: str | Path | None = None,
        snapshot_date: date | None = None,
        currency: str | None = "USD",
        fail_on_review: bool = False,
    ) -> ListingIngestionDryRunResult:
        started_at = _utc_now_iso()
        run_output_dir = self._build_run_output_dir(marketplace_id=marketplace_id)
        preview_dir = run_output_dir / "previews"
        schema_events_path = run_output_dir / "schema_validation_events.jsonl"

        prepared = self._prepare_listing_report(
            marketplace_id=marketplace_id,
            raw_file_path=Path(raw_file_path) if raw_file_path else None,
            snapshot_date=snapshot_date,
            currency=currency,
            preview_dir=preview_dir,
        )
        schema_events = (
            [prepared.schema_validation_event]
            if prepared.schema_validation_event is not None
            else []
        )
        write_jsonl(schema_events_path, schema_events)
        finished_at = _utc_now_iso()
        requires_review = prepared.requires_review
        status = "requires_review" if requires_review else "success"
        if fail_on_review and requires_review:
            status = "failed_requires_review"
        task_audit_event = build_task_audit_event(
            marketplace_id=marketplace_id,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            output_dir=str(run_output_dir),
            report_result=prepared,
        )
        result = ListingIngestionDryRunResult(
            workflow_name="sp_api_listing_ingestion_dry_run",
            marketplace_id=marketplace_id,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            requires_review=requires_review,
            processed_file_count=1 if prepared.raw_file_path else 0,
            parsed_row_count=prepared.parsed_row_count,
            prepared_row_count=prepared.prepared_row_count,
            preview_file_count=1 if prepared.preview_file_path else 0,
            skipped_report_count=1 if prepared.skipped else 0,
            output_dir=str(run_output_dir),
            report_result=prepared,
            task_audit_event=task_audit_event,
        )
        _write_json(run_output_dir / "task_audit_event.json", task_audit_event)
        _write_json(run_output_dir / "listing_ingestion_summary.json", result.to_dict())
        return result

    def _prepare_listing_report(
        self,
        *,
        marketplace_id: str,
        raw_file_path: Path | None,
        snapshot_date: date | None,
        currency: str | None,
        preview_dir: Path,
    ) -> ListingPreparedReportResult:
        path = raw_file_path or find_latest_sp_api_raw_file(
            raw_reports_root=self.raw_reports_root,
            marketplace_id=marketplace_id,
            report_type=LISTING_REPORT_TYPE,
        )
        if path is None:
            return ListingPreparedReportResult(
                report_type=LISTING_REPORT_TYPE,
                target_table=LISTING_TARGET_TABLE_SPEC.target_table,
                raw_file_path=None,
                snapshot_date=None,
                schema_validation_status=None,
                requires_review=True,
                skipped=True,
                skip_reason="raw_file_not_found",
                parsed_row_count=0,
                prepared_row_count=0,
                preview_file_path=None,
                schema_validation_event=None,
            )
        if not path.exists():
            return ListingPreparedReportResult(
                report_type=LISTING_REPORT_TYPE,
                target_table=LISTING_TARGET_TABLE_SPEC.target_table,
                raw_file_path=str(path),
                snapshot_date=None,
                schema_validation_status=None,
                requires_review=True,
                skipped=True,
                skip_reason="raw_file_path_does_not_exist",
                parsed_row_count=0,
                prepared_row_count=0,
                preview_file_path=None,
                schema_validation_event=None,
            )

        analysis = analyze_report_file(
            raw_file_path=str(path),
            report_type=LISTING_REPORT_TYPE,
            marketplace_id=marketplace_id,
            source_system="sp_api_reports",
            redact_sample_values=True,
        )
        schema_result = validate_report_schema(
            analysis=analysis,
            expected_schema=build_listing_expected_schema(),
        )
        schema_event = build_schema_validation_event_row(schema_result)
        effective_snapshot_date = snapshot_date or infer_snapshot_date_from_path(path)
        if schema_result.status in BLOCKING_SCHEMA_STATUSES or schema_result.requires_review:
            return ListingPreparedReportResult(
                report_type=LISTING_REPORT_TYPE,
                target_table=LISTING_TARGET_TABLE_SPEC.target_table,
                raw_file_path=str(path),
                snapshot_date=effective_snapshot_date.isoformat(),
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
            raw_file_path=path,
            marketplace_id=marketplace_id,
            snapshot_date=effective_snapshot_date,
            currency=currency,
            source_report_id=path.stem,
        )
        rows = [map_listing_record_to_table_row(record) for record in records]
        preview_path = preview_dir / f"{LISTING_TARGET_TABLE_SPEC.target_table}.preview.jsonl"
        write_jsonl(preview_path, rows)
        return ListingPreparedReportResult(
            report_type=LISTING_REPORT_TYPE,
            target_table=LISTING_TARGET_TABLE_SPEC.target_table,
            raw_file_path=str(path),
            snapshot_date=effective_snapshot_date.isoformat(),
            schema_validation_status=schema_result.status,
            requires_review=False,
            skipped=False,
            skip_reason=None,
            parsed_row_count=len(records),
            prepared_row_count=len(rows),
            preview_file_path=str(preview_path),
            schema_validation_event=schema_event,
        )

    def _build_run_output_dir(self, *, marketplace_id: str) -> Path:
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        output_dir = (
            self.output_root / LISTING_REPORT_TYPE / _safe_path_part(marketplace_id) / timestamp
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir


def build_listing_expected_schema() -> ExpectedReportSchema:
    return ExpectedReportSchema(
        source_system="sp_api_reports",
        report_type=LISTING_REPORT_TYPE,
        expected_fields=LISTING_TARGET_TABLE_SPEC.expected_fields,
        required_fields=LISTING_TARGET_TABLE_SPEC.required_fields,
        allow_extra_fields=False,
        allow_empty_report=False,
        notes="Listing snapshot flat-file schema observed from GET_MERCHANT_LISTINGS_ALL_DATA.",
    )


def find_latest_sp_api_raw_file(
    *,
    raw_reports_root: str | Path,
    marketplace_id: str,
    report_type: str,
) -> Path | None:
    root = Path(raw_reports_root) / "amazon" / str(marketplace_id) / str(report_type)
    if not root.exists():
        return None
    candidates = [
        path
        for pattern in ("*.txt", "*.tsv", "*.csv")
        for path in root.rglob(pattern)
        if path.is_file()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def infer_snapshot_date_from_path(path: str | Path) -> date:
    for parent in Path(path).parents:
        try:
            return date.fromisoformat(parent.name)
        except ValueError:
            continue
    return datetime.now(UTC).date()


def build_task_audit_event(
    *,
    marketplace_id: str,
    started_at: str,
    finished_at: str,
    status: str,
    output_dir: str,
    report_result: ListingPreparedReportResult,
) -> dict[str, Any]:
    files_created = (1 if report_result.preview_file_path else 0) + 3
    return {
        "workflow_name": "sp_api_listing_ingestion_dry_run",
        "job_name": "prepare_listing_snapshot_ingestion",
        "task_type": "ingestion_dry_run",
        "trigger_type": "manual",
        "run_mode": "local_dry_run",
        "parent_run_id": None,
        "job_execution_id": Path(output_dir).name,
        "marketplace_id": marketplace_id,
        "source_system": "sp_api_reports",
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": _duration_ms(started_at, finished_at),
        "date_start": report_result.snapshot_date,
        "date_end": report_result.snapshot_date,
        "rows_read": report_result.parsed_row_count,
        "rows_written": report_result.prepared_row_count,
        "rows_skipped": 1 if report_result.skipped else 0,
        "rows_failed": 0,
        "files_created": files_created,
        "retry_count": 0,
        "config_snapshot_json": json.dumps(
            {
                "marketplace_id": marketplace_id,
                "output_dir": output_dir,
                "report_type": LISTING_REPORT_TYPE,
                "raw_file_path": report_result.raw_file_path,
                "snapshot_date": report_result.snapshot_date,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        "message": _build_task_message(report_result),
        "error_type": None,
        "error_detail": None,
    }


def _build_task_message(report_result: ListingPreparedReportResult) -> str:
    if report_result.requires_review:
        return f"Requires review: {LISTING_REPORT_TYPE}"
    return f"Prepared Listing DB-ready preview rows: {report_result.prepared_row_count}"


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
    "ListingIngestionDryRunResult",
    "ListingIngestionDryRunService",
    "ListingPreparedReportResult",
    "build_listing_expected_schema",
    "build_task_audit_event",
    "find_latest_sp_api_raw_file",
    "infer_snapshot_date_from_path",
]
