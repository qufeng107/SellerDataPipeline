from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from seller_data_pipeline.ingestion.ads_ingestion_dry_run import (
    build_schema_validation_event_row,
)
from seller_data_pipeline.ingestion.inventory_ledger_table_mapping import (
    LEDGER_DETAIL_EXPECTED_FIELDS,
    LEDGER_DETAIL_REQUIRED_FIELDS_TUPLE,
    LEDGER_DETAIL_TARGET_TABLE_SPEC,
    LEDGER_SUMMARY_EXPECTED_FIELDS,
    LEDGER_SUMMARY_REQUIRED_FIELDS_TUPLE,
    LEDGER_SUMMARY_TARGET_TABLE_SPEC,
    InventoryLedgerTargetTableSpec,
    map_inventory_ledger_detail_record_to_table_row,
    map_inventory_ledger_summary_record_to_table_row,
    write_jsonl,
)
from seller_data_pipeline.parsers.amazon.inventory_ledger_parser import (
    LEDGER_DETAIL_REPORT_TYPE,
    LEDGER_SUMMARY_REPORT_TYPE,
    InventoryLedgerDetailParser,
    InventoryLedgerSummaryParser,
)
from seller_data_pipeline.sampling.report_analyzer import analyze_report_file
from seller_data_pipeline.sampling.schema_drift import (
    BLOCKING_SCHEMA_STATUSES,
    ExpectedReportSchema,
    validate_report_schema,
)


@dataclass(frozen=True)
class InventoryLedgerPreparedReportResult:
    report_type: str
    raw_file_path: str | None
    schema_validation_status: str | None
    requires_review: bool
    skipped: bool
    skip_reason: str | None
    parsed_row_count: int
    prepared_row_count: int
    table_row_counts: dict[str, int]
    preview_file_paths: dict[str, str]
    schema_validation_event: dict[str, Any] | None


@dataclass(frozen=True)
class InventoryLedgerIngestionDryRunResult:
    workflow_name: str
    marketplace_id: str
    started_at: str
    finished_at: str
    status: str
    requires_review: bool
    processed_report_count: int
    parsed_row_count: int
    prepared_row_count: int
    preview_file_count: int
    skipped_report_count: int
    output_dir: str
    report_results: tuple[InventoryLedgerPreparedReportResult, ...]
    task_audit_event: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(asdict(self), ensure_ascii=False, default=str))


class InventoryLedgerIngestionDryRunService:
    """Prepare DB-ready Inventory Ledger preview rows without writing to Azure SQL."""

    def __init__(
        self,
        *,
        raw_reports_root: str | Path,
        output_root: str | Path = "runtime/ingestion/sp_api",
    ) -> None:
        self.raw_reports_root = Path(raw_reports_root)
        self.output_root = Path(output_root)
        self.summary_parser = InventoryLedgerSummaryParser()
        self.detail_parser = InventoryLedgerDetailParser()

    def prepare(
        self,
        *,
        marketplace_id: str,
        summary_raw_file_path: str | Path | None = None,
        detail_raw_file_path: str | Path | None = None,
        fail_on_review: bool = True,
    ) -> InventoryLedgerIngestionDryRunResult:
        started_at = _utc_now_iso()
        output_dir = self._build_run_output_dir(marketplace_id=marketplace_id)
        preview_dir = output_dir / "previews"
        schema_events_path = output_dir / "schema_validation_events.jsonl"
        report_results = (
            self._prepare_summary_report(
                marketplace_id=marketplace_id,
                raw_file_path=Path(summary_raw_file_path) if summary_raw_file_path else None,
                preview_dir=preview_dir,
            ),
            self._prepare_detail_report(
                marketplace_id=marketplace_id,
                raw_file_path=Path(detail_raw_file_path) if detail_raw_file_path else None,
                preview_dir=preview_dir,
            ),
        )
        requires_review = any(item.requires_review for item in report_results)
        status = "requires_review" if requires_review else "success"
        finished_at = _utc_now_iso()
        task_audit_event = build_task_audit_event(
            marketplace_id=marketplace_id,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            output_dir=str(output_dir),
            report_results=report_results,
        )
        result = InventoryLedgerIngestionDryRunResult(
            workflow_name="sp_api_inventory_ledger_ingestion_dry_run",
            marketplace_id=marketplace_id,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            requires_review=requires_review,
            processed_report_count=sum(0 if item.skipped else 1 for item in report_results),
            parsed_row_count=sum(item.parsed_row_count for item in report_results),
            prepared_row_count=sum(item.prepared_row_count for item in report_results),
            preview_file_count=sum(len(item.preview_file_paths) for item in report_results),
            skipped_report_count=sum(1 for item in report_results if item.skipped),
            output_dir=str(output_dir),
            report_results=report_results,
            task_audit_event=task_audit_event,
        )
        _write_json(output_dir / "inventory_ledger_ingestion_dry_run_result.json", result.to_dict())
        _write_json(output_dir / "task_audit_event.json", task_audit_event)
        schema_events = [
            item.schema_validation_event for item in report_results if item.schema_validation_event
        ]
        write_jsonl(schema_events_path, schema_events)
        if requires_review and fail_on_review:
            return result
        return result

    def _prepare_summary_report(
        self,
        *,
        marketplace_id: str,
        raw_file_path: Path | None,
        preview_dir: Path,
    ) -> InventoryLedgerPreparedReportResult:
        selected_path = raw_file_path or find_latest_sp_api_raw_file(
            raw_reports_root=self.raw_reports_root,
            marketplace_id=marketplace_id,
            report_type=LEDGER_SUMMARY_REPORT_TYPE,
        )
        if selected_path is None:
            return _skipped_result(
                report_type=LEDGER_SUMMARY_REPORT_TYPE,
                raw_file_path=None,
                skip_reason="raw_file_not_found",
                requires_review=True,
            )
        if not selected_path.exists():
            return _skipped_result(
                report_type=LEDGER_SUMMARY_REPORT_TYPE,
                raw_file_path=str(selected_path),
                skip_reason="raw_file_path_does_not_exist",
                requires_review=True,
            )
        schema_event, requires_review, status = _validate_raw_schema(
            raw_file_path=selected_path,
            marketplace_id=marketplace_id,
            expected_schema=build_summary_expected_schema(),
        )
        if requires_review:
            return _schema_review_result(
                report_type=LEDGER_SUMMARY_REPORT_TYPE,
                raw_file_path=selected_path,
                status=status,
                schema_event=schema_event,
            )
        records = self.summary_parser.parse_file(
            raw_file_path=selected_path,
            marketplace_id=marketplace_id,
            source_report_id=selected_path.stem,
        )
        rows = [
            map_inventory_ledger_summary_record_to_table_row(record, source_row_index=index)
            for index, record in enumerate(records, start=1)
        ]
        return _write_previews_or_review(
            report_type=LEDGER_SUMMARY_REPORT_TYPE,
            raw_file_path=selected_path,
            schema_validation_status=status,
            schema_event=schema_event,
            table_rows={LEDGER_SUMMARY_TARGET_TABLE_SPEC.target_table: rows},
            table_specs={
                LEDGER_SUMMARY_TARGET_TABLE_SPEC.target_table: LEDGER_SUMMARY_TARGET_TABLE_SPEC
            },
            preview_dir=preview_dir,
        )

    def _prepare_detail_report(
        self,
        *,
        marketplace_id: str,
        raw_file_path: Path | None,
        preview_dir: Path,
    ) -> InventoryLedgerPreparedReportResult:
        selected_path = raw_file_path or find_latest_sp_api_raw_file(
            raw_reports_root=self.raw_reports_root,
            marketplace_id=marketplace_id,
            report_type=LEDGER_DETAIL_REPORT_TYPE,
        )
        if selected_path is None:
            return _skipped_result(
                report_type=LEDGER_DETAIL_REPORT_TYPE,
                raw_file_path=None,
                skip_reason="raw_file_not_found",
                requires_review=True,
            )
        if not selected_path.exists():
            return _skipped_result(
                report_type=LEDGER_DETAIL_REPORT_TYPE,
                raw_file_path=str(selected_path),
                skip_reason="raw_file_path_does_not_exist",
                requires_review=True,
            )
        schema_event, requires_review, status = _validate_raw_schema(
            raw_file_path=selected_path,
            marketplace_id=marketplace_id,
            expected_schema=build_detail_expected_schema(),
        )
        if requires_review:
            return _schema_review_result(
                report_type=LEDGER_DETAIL_REPORT_TYPE,
                raw_file_path=selected_path,
                status=status,
                schema_event=schema_event,
            )
        records = self.detail_parser.parse_file(
            raw_file_path=selected_path,
            marketplace_id=marketplace_id,
            source_report_id=selected_path.stem,
        )
        rows = [
            map_inventory_ledger_detail_record_to_table_row(record, source_row_index=index)
            for index, record in enumerate(records, start=1)
        ]
        return _write_previews_or_review(
            report_type=LEDGER_DETAIL_REPORT_TYPE,
            raw_file_path=selected_path,
            schema_validation_status=status,
            schema_event=schema_event,
            table_rows={LEDGER_DETAIL_TARGET_TABLE_SPEC.target_table: rows},
            table_specs={
                LEDGER_DETAIL_TARGET_TABLE_SPEC.target_table: LEDGER_DETAIL_TARGET_TABLE_SPEC
            },
            preview_dir=preview_dir,
        )

    def _build_run_output_dir(self, *, marketplace_id: str) -> Path:
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        output_dir = (
            self.output_root / "INVENTORY_LEDGER" / _safe_path_part(marketplace_id) / timestamp
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir


def build_summary_expected_schema() -> ExpectedReportSchema:
    return ExpectedReportSchema(
        source_system="sp_api_reports",
        report_type=LEDGER_SUMMARY_REPORT_TYPE,
        expected_fields=LEDGER_SUMMARY_EXPECTED_FIELDS,
        required_fields=LEDGER_SUMMARY_REQUIRED_FIELDS_TUPLE,
        allow_extra_fields=False,
        allow_empty_report=True,
        notes=(
            "Inventory Ledger summary flat-file schema observed from GET_LEDGER_SUMMARY_VIEW_DATA."
        ),
    )


def build_detail_expected_schema() -> ExpectedReportSchema:
    return ExpectedReportSchema(
        source_system="sp_api_reports",
        report_type=LEDGER_DETAIL_REPORT_TYPE,
        expected_fields=LEDGER_DETAIL_EXPECTED_FIELDS,
        required_fields=LEDGER_DETAIL_REQUIRED_FIELDS_TUPLE,
        allow_extra_fields=False,
        allow_empty_report=True,
        notes="Inventory Ledger detail flat-file schema observed from GET_LEDGER_DETAIL_VIEW_DATA.",
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
    candidates = [path for path in root.rglob("*.txt") if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def detect_duplicate_business_key_conflict(rows: list[dict[str, Any]]) -> str | None:
    seen: dict[str, str | None] = {}
    for row in rows:
        key_hash = str(row.get("business_key_hash") or "")
        source_hash = row.get("source_row_hash")
        if not key_hash:
            return "missing_business_key_hash"
        if key_hash in seen and seen[key_hash] != source_hash:
            return f"duplicate business_key_hash has different source_row_hash: {key_hash}"
        seen[key_hash] = str(source_hash) if source_hash is not None else None
    return None


def build_task_audit_event(
    *,
    marketplace_id: str,
    started_at: str,
    finished_at: str,
    status: str,
    output_dir: str,
    report_results: tuple[InventoryLedgerPreparedReportResult, ...],
) -> dict[str, Any]:
    files_created = sum(len(item.preview_file_paths) for item in report_results) + 3
    return {
        "workflow_name": "sp_api_inventory_ledger_ingestion_dry_run",
        "job_name": "prepare_inventory_ledger_ingestion",
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
        "rows_read": sum(item.parsed_row_count for item in report_results),
        "rows_written": sum(item.prepared_row_count for item in report_results),
        "rows_skipped": sum(1 for item in report_results if item.skipped),
        "rows_failed": 0,
        "files_created": files_created,
        "retry_count": 0,
        "config_snapshot_json": json.dumps(
            {
                "marketplace_id": marketplace_id,
                "output_dir": output_dir,
                "report_types": [LEDGER_SUMMARY_REPORT_TYPE, LEDGER_DETAIL_REPORT_TYPE],
                "raw_file_paths": [item.raw_file_path for item in report_results],
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        "message": _build_task_message(report_results),
        "error_type": None,
        "error_detail": None,
    }


def _validate_raw_schema(
    *,
    raw_file_path: Path,
    marketplace_id: str,
    expected_schema: ExpectedReportSchema,
) -> tuple[dict[str, Any], bool, str]:
    analysis = analyze_report_file(
        raw_file_path=str(raw_file_path),
        report_type=expected_schema.report_type,
        marketplace_id=marketplace_id,
        source_system="sp_api_reports",
        redact_sample_values=True,
    )
    schema_result = validate_report_schema(
        analysis=analysis,
        expected_schema=expected_schema,
    )
    event = build_schema_validation_event_row(schema_result)
    requires_review = (
        schema_result.status in BLOCKING_SCHEMA_STATUSES or schema_result.requires_review
    )
    return event, requires_review, schema_result.status


def _write_previews_or_review(
    *,
    report_type: str,
    raw_file_path: Path,
    schema_validation_status: str,
    schema_event: dict[str, Any],
    table_rows: dict[str, list[dict[str, Any]]],
    table_specs: dict[str, InventoryLedgerTargetTableSpec],
    preview_dir: Path,
) -> InventoryLedgerPreparedReportResult:
    for table_name, rows in table_rows.items():
        duplicate_issue = detect_duplicate_business_key_conflict(rows)
        if duplicate_issue:
            return InventoryLedgerPreparedReportResult(
                report_type=report_type,
                raw_file_path=str(raw_file_path),
                schema_validation_status="duplicate_business_key_requires_review",
                requires_review=True,
                skipped=True,
                skip_reason=(
                    f"duplicate_business_key_requires_review:{table_name}:{duplicate_issue}"
                ),
                parsed_row_count=sum(len(items) for items in table_rows.values()),
                prepared_row_count=0,
                table_row_counts={},
                preview_file_paths={},
                schema_validation_event=_with_duplicate_key_review(
                    schema_event, table_name, duplicate_issue
                ),
            )
    preview_paths: dict[str, str] = {}
    table_row_counts: dict[str, int] = {}
    for table_name, rows in table_rows.items():
        table_row_counts[table_name] = len(rows)
        if rows:
            preview_path = preview_dir / f"{table_name}.preview.jsonl"
            write_jsonl(preview_path, rows)
            preview_paths[table_name] = str(preview_path)
        elif table_specs[table_name].target_table:
            continue
    return InventoryLedgerPreparedReportResult(
        report_type=report_type,
        raw_file_path=str(raw_file_path),
        schema_validation_status=schema_validation_status,
        requires_review=False,
        skipped=False,
        skip_reason=None,
        parsed_row_count=sum(len(items) for items in table_rows.values()),
        prepared_row_count=sum(len(items) for items in table_rows.values()),
        table_row_counts=table_row_counts,
        preview_file_paths=preview_paths,
        schema_validation_event=schema_event,
    )


def _skipped_result(
    *,
    report_type: str,
    raw_file_path: str | None,
    skip_reason: str,
    requires_review: bool,
) -> InventoryLedgerPreparedReportResult:
    return InventoryLedgerPreparedReportResult(
        report_type=report_type,
        raw_file_path=raw_file_path,
        schema_validation_status=None,
        requires_review=requires_review,
        skipped=True,
        skip_reason=skip_reason,
        parsed_row_count=0,
        prepared_row_count=0,
        table_row_counts={},
        preview_file_paths={},
        schema_validation_event=None,
    )


def _schema_review_result(
    *,
    report_type: str,
    raw_file_path: Path,
    status: str,
    schema_event: dict[str, Any],
) -> InventoryLedgerPreparedReportResult:
    return InventoryLedgerPreparedReportResult(
        report_type=report_type,
        raw_file_path=str(raw_file_path),
        schema_validation_status=status,
        requires_review=True,
        skipped=True,
        skip_reason="schema_validation_requires_review",
        parsed_row_count=0,
        prepared_row_count=0,
        table_row_counts={},
        preview_file_paths={},
        schema_validation_event=schema_event,
    )


def _with_duplicate_key_review(
    event: dict[str, Any],
    table_name: str,
    reason: str,
) -> dict[str, Any]:
    payload = dict(event)
    payload.update(
        {
            "validation_status": "duplicate_business_key_requires_review",
            "severity": "warning",
            "requires_review": True,
            "notification_status": "pending",
            "message": (
                "Inventory Ledger dry-run detected duplicate business keys requiring "
                f"review in {table_name}: {reason}"
            ),
        }
    )
    return payload


def _build_task_message(report_results: tuple[InventoryLedgerPreparedReportResult, ...]) -> str:
    if any(item.requires_review for item in report_results):
        return "Inventory Ledger ingestion dry-run requires review before database writes."
    return "Inventory Ledger ingestion dry-run prepared DB-ready preview rows."


def _duration_ms(started_at: str, finished_at: str) -> int:
    start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    finish = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
    return int((finish - start).total_seconds() * 1000)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _safe_path_part(value: str) -> str:
    safe = "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "_" for char in str(value)
    )
    return safe[:120] or "unknown"


def _write_json(path: str | Path, payload: Any) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    return output_path


__all__ = [
    "InventoryLedgerIngestionDryRunResult",
    "InventoryLedgerIngestionDryRunService",
    "InventoryLedgerPreparedReportResult",
    "build_detail_expected_schema",
    "build_summary_expected_schema",
    "detect_duplicate_business_key_conflict",
    "find_latest_sp_api_raw_file",
]
