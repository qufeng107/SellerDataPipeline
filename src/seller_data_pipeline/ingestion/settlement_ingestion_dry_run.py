from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from seller_data_pipeline.ingestion.ads_ingestion_dry_run import (
    BLOCKING_SCHEMA_STATUSES,
    build_schema_validation_event_row,
)
from seller_data_pipeline.ingestion.settlement_table_mapping import (
    SETTLEMENT_TARGET_TABLE_SPEC,
    map_settlement_record_to_table_row,
    write_jsonl,
)
from seller_data_pipeline.parsers.amazon.settlement_report_parser import (
    SETTLEMENT_V2_REPORT_TYPE,
    SettlementReportParser,
)
from seller_data_pipeline.sampling.report_analyzer import analyze_report_file
from seller_data_pipeline.sampling.schema_drift import ExpectedReportSchema, validate_report_schema


@dataclass(frozen=True)
class SettlementPreparedFileResult:
    report_type: str
    target_table: str
    raw_file_path: str | None
    schema_validation_status: str | None
    requires_review: bool
    skipped: bool
    skip_reason: str | None
    parsed_row_count: int
    prepared_row_count: int
    schema_validation_event: dict[str, Any] | None


@dataclass(frozen=True)
class SettlementIngestionDryRunResult:
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
    skipped_file_count: int
    output_dir: str
    preview_file_path: str | None
    file_results: tuple[SettlementPreparedFileResult, ...]
    schema_validation_events: tuple[dict[str, Any], ...]
    task_audit_event: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(asdict(self), ensure_ascii=False, default=str))


class SettlementIngestionDryRunService:
    """Prepare DB-ready Settlement rows locally without touching Azure SQL."""

    def __init__(
        self,
        *,
        raw_reports_root: str | Path,
        output_root: str | Path = "runtime/ingestion/sp_api",
    ) -> None:
        self.raw_reports_root = Path(raw_reports_root)
        self.output_root = Path(output_root)
        self.parser = SettlementReportParser()

    def prepare(
        self,
        *,
        marketplace_id: str,
        raw_file_paths: list[str | Path] | None = None,
        fail_on_review: bool = False,
    ) -> SettlementIngestionDryRunResult:
        started_at = _utc_now_iso()
        run_output_dir = self._build_run_output_dir(marketplace_id=marketplace_id)
        preview_dir = run_output_dir / "previews"
        preview_path = preview_dir / f"{SETTLEMENT_TARGET_TABLE_SPEC.target_table}.preview.jsonl"
        schema_events_path = run_output_dir / "schema_validation_events.jsonl"

        paths = _resolve_raw_file_paths(
            raw_reports_root=self.raw_reports_root,
            marketplace_id=marketplace_id,
            raw_file_paths=raw_file_paths,
        )
        if not paths:
            file_results = (
                SettlementPreparedFileResult(
                    report_type=SETTLEMENT_V2_REPORT_TYPE,
                    target_table=SETTLEMENT_TARGET_TABLE_SPEC.target_table,
                    raw_file_path=None,
                    schema_validation_status=None,
                    requires_review=True,
                    skipped=True,
                    skip_reason="raw_file_not_found",
                    parsed_row_count=0,
                    prepared_row_count=0,
                    schema_validation_event=None,
                ),
            )
            return self._finalize_result(
                marketplace_id=marketplace_id,
                started_at=started_at,
                run_output_dir=run_output_dir,
                preview_file_path=None,
                rows=[],
                file_results=file_results,
                schema_events=[],
                fail_on_review=fail_on_review,
            )

        all_rows: list[dict[str, Any]] = []
        file_results: list[SettlementPreparedFileResult] = []
        schema_events: list[dict[str, Any]] = []
        for path in paths:
            prepared = self._prepare_one_file(
                marketplace_id=marketplace_id,
                raw_file_path=path,
                rows_out=all_rows,
            )
            file_results.append(prepared)
            if prepared.schema_validation_event is not None:
                schema_events.append(prepared.schema_validation_event)

        preview_file_path: str | None = None
        if all_rows:
            write_jsonl(preview_path, all_rows)
            preview_file_path = str(preview_path)
        write_jsonl(schema_events_path, schema_events)
        return self._finalize_result(
            marketplace_id=marketplace_id,
            started_at=started_at,
            run_output_dir=run_output_dir,
            preview_file_path=preview_file_path,
            rows=all_rows,
            file_results=tuple(file_results),
            schema_events=schema_events,
            fail_on_review=fail_on_review,
        )

    def _prepare_one_file(
        self,
        *,
        marketplace_id: str,
        raw_file_path: Path,
        rows_out: list[dict[str, Any]],
    ) -> SettlementPreparedFileResult:
        if not raw_file_path.exists():
            return SettlementPreparedFileResult(
                report_type=SETTLEMENT_V2_REPORT_TYPE,
                target_table=SETTLEMENT_TARGET_TABLE_SPEC.target_table,
                raw_file_path=str(raw_file_path),
                schema_validation_status=None,
                requires_review=True,
                skipped=True,
                skip_reason="raw_file_path_does_not_exist",
                parsed_row_count=0,
                prepared_row_count=0,
                schema_validation_event=None,
            )

        analysis = analyze_report_file(
            raw_file_path=str(raw_file_path),
            report_type=SETTLEMENT_V2_REPORT_TYPE,
            marketplace_id=marketplace_id,
            source_system="sp_api_reports",
            redact_sample_values=True,
        )
        schema_result = validate_report_schema(
            analysis=analysis,
            expected_schema=build_settlement_expected_schema(),
        )
        schema_event = build_schema_validation_event_row(schema_result)
        if schema_result.status in BLOCKING_SCHEMA_STATUSES or schema_result.requires_review:
            return SettlementPreparedFileResult(
                report_type=SETTLEMENT_V2_REPORT_TYPE,
                target_table=SETTLEMENT_TARGET_TABLE_SPEC.target_table,
                raw_file_path=str(raw_file_path),
                schema_validation_status=schema_result.status,
                requires_review=True,
                skipped=True,
                skip_reason="schema_validation_requires_review",
                parsed_row_count=0,
                prepared_row_count=0,
                schema_validation_event=schema_event,
            )

        records = self.parser.parse_file(
            raw_file_path=raw_file_path,
            marketplace_id=marketplace_id,
            source_report_id=raw_file_path.stem,
        )
        start_len = len(rows_out)
        for source_row_index, record in enumerate(records, start=1):
            rows_out.append(
                map_settlement_record_to_table_row(
                    record,
                    source_row_index=source_row_index,
                )
            )
        prepared_count = len(rows_out) - start_len
        return SettlementPreparedFileResult(
            report_type=SETTLEMENT_V2_REPORT_TYPE,
            target_table=SETTLEMENT_TARGET_TABLE_SPEC.target_table,
            raw_file_path=str(raw_file_path),
            schema_validation_status=schema_result.status,
            requires_review=False,
            skipped=False,
            skip_reason=None,
            parsed_row_count=len(records),
            prepared_row_count=prepared_count,
            schema_validation_event=schema_event,
        )

    def _finalize_result(
        self,
        *,
        marketplace_id: str,
        started_at: str,
        run_output_dir: Path,
        preview_file_path: str | None,
        rows: list[dict[str, Any]],
        file_results: tuple[SettlementPreparedFileResult, ...],
        schema_events: list[dict[str, Any]],
        fail_on_review: bool,
    ) -> SettlementIngestionDryRunResult:
        finished_at = _utc_now_iso()
        requires_review = any(result.requires_review for result in file_results)
        status = "requires_review" if requires_review else "success"
        if fail_on_review and requires_review:
            status = "failed_requires_review"
        task_audit_event = build_task_audit_event(
            marketplace_id=marketplace_id,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            output_dir=str(run_output_dir),
            file_results=file_results,
            preview_file_path=preview_file_path,
        )
        result = SettlementIngestionDryRunResult(
            workflow_name="sp_api_settlement_ingestion_dry_run",
            marketplace_id=marketplace_id,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            requires_review=requires_review,
            processed_file_count=sum(1 for item in file_results if item.raw_file_path),
            parsed_row_count=sum(item.parsed_row_count for item in file_results),
            prepared_row_count=len(rows),
            preview_file_count=1 if preview_file_path else 0,
            skipped_file_count=sum(1 for item in file_results if item.skipped),
            output_dir=str(run_output_dir),
            preview_file_path=preview_file_path,
            file_results=file_results,
            schema_validation_events=tuple(schema_events),
            task_audit_event=task_audit_event,
        )
        _write_json(run_output_dir / "task_audit_event.json", task_audit_event)
        _write_json(run_output_dir / "settlement_ingestion_summary.json", result.to_dict())
        return result

    def _build_run_output_dir(self, *, marketplace_id: str) -> Path:
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        output_dir = (
            self.output_root
            / SETTLEMENT_V2_REPORT_TYPE
            / _safe_path_part(marketplace_id)
            / timestamp
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir


def build_settlement_expected_schema() -> ExpectedReportSchema:
    return ExpectedReportSchema(
        source_system="sp_api_reports",
        report_type=SETTLEMENT_V2_REPORT_TYPE,
        expected_fields=SETTLEMENT_TARGET_TABLE_SPEC.expected_fields,
        required_fields=SETTLEMENT_TARGET_TABLE_SPEC.required_fields,
        allow_extra_fields=False,
        allow_empty_report=False,
        notes=(
            "Settlement flat-file schema observed from GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2."
        ),
    )


def find_all_sp_api_raw_files(
    *,
    raw_reports_root: str | Path,
    marketplace_id: str,
    report_type: str,
) -> list[Path]:
    root = Path(raw_reports_root) / "amazon" / str(marketplace_id) / str(report_type)
    if not root.exists():
        return []
    candidates = [
        path
        for pattern in ("*.txt", "*.tsv", "*.csv")
        for path in root.rglob(pattern)
        if path.is_file()
    ]
    return sorted(candidates, key=lambda path: str(path))


def build_task_audit_event(
    *,
    marketplace_id: str,
    started_at: str,
    finished_at: str,
    status: str,
    output_dir: str,
    file_results: tuple[SettlementPreparedFileResult, ...],
    preview_file_path: str | None,
) -> dict[str, Any]:
    files_created = (1 if preview_file_path else 0) + 3
    return {
        "workflow_name": "sp_api_settlement_ingestion_dry_run",
        "job_name": "prepare_settlement_ingestion",
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
        "date_start": None,
        "date_end": None,
        "rows_read": sum(item.parsed_row_count for item in file_results),
        "rows_written": sum(item.prepared_row_count for item in file_results),
        "rows_skipped": sum(1 for item in file_results if item.skipped),
        "rows_failed": 0,
        "files_created": files_created,
        "retry_count": 0,
        "config_snapshot_json": json.dumps(
            {
                "marketplace_id": marketplace_id,
                "output_dir": output_dir,
                "report_type": SETTLEMENT_V2_REPORT_TYPE,
                "raw_file_paths": [
                    item.raw_file_path for item in file_results if item.raw_file_path
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        "message": _build_task_message(file_results),
        "error_type": None,
        "error_detail": None,
    }


def _resolve_raw_file_paths(
    *,
    raw_reports_root: Path,
    marketplace_id: str,
    raw_file_paths: list[str | Path] | None,
) -> list[Path]:
    if raw_file_paths:
        return [Path(path) for path in raw_file_paths]
    return find_all_sp_api_raw_files(
        raw_reports_root=raw_reports_root,
        marketplace_id=marketplace_id,
        report_type=SETTLEMENT_V2_REPORT_TYPE,
    )


def _build_task_message(file_results: tuple[SettlementPreparedFileResult, ...]) -> str:
    if any(result.requires_review for result in file_results):
        return f"Requires review: {SETTLEMENT_V2_REPORT_TYPE}"
    prepared_rows = sum(item.prepared_row_count for item in file_results)
    return f"Prepared Settlement DB-ready preview rows: {prepared_rows}"


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
    "SettlementIngestionDryRunResult",
    "SettlementIngestionDryRunService",
    "SettlementPreparedFileResult",
    "build_settlement_expected_schema",
    "build_task_audit_event",
    "find_all_sp_api_raw_files",
]
