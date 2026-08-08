from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from seller_data_pipeline.ingestion.ads_ingestion_dry_run import (
    build_schema_validation_event_row,
)
from seller_data_pipeline.ingestion.sales_traffic_table_mapping import (
    SALES_AND_TRAFFIC_REPORT_TYPE,
    SALES_TRAFFIC_ASIN_TABLE_SPEC,
    SALES_TRAFFIC_DAILY_TABLE_SPEC,
    map_sales_traffic_asin_record_to_table_row,
    map_sales_traffic_date_record_to_table_row,
    write_jsonl,
)
from seller_data_pipeline.parsers.amazon.sales_report_parser import SalesReportParser
from seller_data_pipeline.sampling.report_analyzer import analyze_report_file
from seller_data_pipeline.sampling.schema_drift import (
    BLOCKING_SCHEMA_STATUSES,
    ExpectedReportSchema,
    validate_report_schema,
)


@dataclass(frozen=True)
class SalesTrafficPreparedTableResult:
    report_type: str
    target_table: str
    raw_file_path: str | None
    schema_validation_status: str | None
    requires_review: bool
    skipped: bool
    skip_reason: str | None
    parsed_row_count: int
    prepared_row_count: int
    preview_file_path: str | None


@dataclass(frozen=True)
class SalesTrafficIngestionDryRunResult:
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
    skipped_table_count: int
    output_dir: str
    raw_file_path: str | None
    report_start_date: str | None
    report_end_date: str | None
    schema_validation_status: str | None
    table_results: tuple[SalesTrafficPreparedTableResult, ...]
    schema_validation_event: dict[str, Any] | None
    task_audit_event: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(asdict(self), ensure_ascii=False, default=str))


class SalesTrafficIngestionDryRunService:
    """Prepare DB-ready Sales & Traffic rows locally without touching Azure SQL."""

    def __init__(
        self,
        *,
        raw_reports_root: str | Path,
        output_root: str | Path = "runtime/ingestion/sp_api",
    ) -> None:
        self.raw_reports_root = Path(raw_reports_root)
        self.output_root = Path(output_root)
        self.parser = SalesReportParser()

    def prepare(
        self,
        *,
        marketplace_id: str,
        raw_file_path: str | Path | None = None,
        fail_on_review: bool = False,
    ) -> SalesTrafficIngestionDryRunResult:
        started_at = _utc_now_iso()
        run_output_dir = self._build_run_output_dir(marketplace_id=marketplace_id)
        preview_dir = run_output_dir / "previews"
        schema_events_path = run_output_dir / "schema_validation_events.jsonl"

        path = (
            Path(raw_file_path)
            if raw_file_path
            else find_latest_sp_api_raw_file(
                raw_reports_root=self.raw_reports_root,
                marketplace_id=marketplace_id,
                report_type=SALES_AND_TRAFFIC_REPORT_TYPE,
            )
        )
        if path is None:
            return self._build_missing_file_result(
                marketplace_id=marketplace_id,
                started_at=started_at,
                run_output_dir=run_output_dir,
                skip_reason="raw_file_not_found",
            )
        if not path.exists():
            return self._build_missing_file_result(
                marketplace_id=marketplace_id,
                started_at=started_at,
                run_output_dir=run_output_dir,
                raw_file_path=str(path),
                skip_reason="raw_file_path_does_not_exist",
            )

        analysis = analyze_report_file(
            raw_file_path=str(path),
            report_type=SALES_AND_TRAFFIC_REPORT_TYPE,
            marketplace_id=marketplace_id,
            source_system="sp_api_reports",
            redact_sample_values=True,
        )
        schema_result = validate_report_schema(
            analysis=analysis,
            expected_schema=build_sales_traffic_expected_schema(),
        )
        schema_event = build_schema_validation_event_row(schema_result)

        parsed = self.parser.parse_file(
            raw_file_path=path,
            marketplace_id=marketplace_id,
            source_report_id=path.stem,
        )
        report_start_date = _empty_to_none(parsed.report_specification.get("dataStartTime"))
        report_end_date = _empty_to_none(parsed.report_specification.get("dataEndTime"))
        option_review_message = _validate_supported_report_options(parsed.report_specification)
        if option_review_message:
            schema_event = dict(schema_event)
            schema_event.update(
                {
                    "validation_status": "unsupported_report_options",
                    "severity": "warning",
                    "requires_review": True,
                    "notification_status": "pending",
                    "message": option_review_message,
                }
            )
        write_jsonl(schema_events_path, [schema_event])

        if (
            schema_result.status in BLOCKING_SCHEMA_STATUSES
            or schema_result.requires_review
            or bool(option_review_message)
        ):
            table_results = (
                SalesTrafficPreparedTableResult(
                    report_type=SALES_AND_TRAFFIC_REPORT_TYPE,
                    target_table=SALES_TRAFFIC_DAILY_TABLE_SPEC.target_table,
                    raw_file_path=str(path),
                    schema_validation_status=str(
                        schema_event.get("validation_status") or schema_result.status
                    ),
                    requires_review=True,
                    skipped=True,
                    skip_reason="schema_validation_requires_review",
                    parsed_row_count=0,
                    prepared_row_count=0,
                    preview_file_path=None,
                ),
                SalesTrafficPreparedTableResult(
                    report_type=SALES_AND_TRAFFIC_REPORT_TYPE,
                    target_table=SALES_TRAFFIC_ASIN_TABLE_SPEC.target_table,
                    raw_file_path=str(path),
                    schema_validation_status=str(
                        schema_event.get("validation_status") or schema_result.status
                    ),
                    requires_review=True,
                    skipped=True,
                    skip_reason="schema_validation_requires_review",
                    parsed_row_count=0,
                    prepared_row_count=0,
                    preview_file_path=None,
                ),
            )
            return self._finalize_result(
                marketplace_id=marketplace_id,
                started_at=started_at,
                run_output_dir=run_output_dir,
                raw_file_path=str(path),
                report_start_date=report_start_date,
                report_end_date=report_end_date,
                schema_validation_status=str(
                    schema_event.get("validation_status") or schema_result.status
                ),
                requires_review=True,
                table_results=table_results,
                schema_validation_event=schema_event,
                fail_on_review=fail_on_review,
            )

        daily_rows = [
            map_sales_traffic_date_record_to_table_row(record) for record in parsed.by_date
        ]
        asin_rows = [
            map_sales_traffic_asin_record_to_table_row(record) for record in parsed.by_asin
        ]
        daily_preview_path = (
            preview_dir / f"{SALES_TRAFFIC_DAILY_TABLE_SPEC.target_table}.preview.jsonl"
        )
        asin_preview_path = (
            preview_dir / f"{SALES_TRAFFIC_ASIN_TABLE_SPEC.target_table}.preview.jsonl"
        )
        write_jsonl(daily_preview_path, daily_rows)
        write_jsonl(asin_preview_path, asin_rows)
        table_results = (
            SalesTrafficPreparedTableResult(
                report_type=SALES_AND_TRAFFIC_REPORT_TYPE,
                target_table=SALES_TRAFFIC_DAILY_TABLE_SPEC.target_table,
                raw_file_path=str(path),
                schema_validation_status=str(
                    schema_event.get("validation_status") or schema_result.status
                ),
                requires_review=False,
                skipped=False,
                skip_reason=None,
                parsed_row_count=len(parsed.by_date),
                prepared_row_count=len(daily_rows),
                preview_file_path=str(daily_preview_path),
            ),
            SalesTrafficPreparedTableResult(
                report_type=SALES_AND_TRAFFIC_REPORT_TYPE,
                target_table=SALES_TRAFFIC_ASIN_TABLE_SPEC.target_table,
                raw_file_path=str(path),
                schema_validation_status=str(
                    schema_event.get("validation_status") or schema_result.status
                ),
                requires_review=False,
                skipped=False,
                skip_reason=None,
                parsed_row_count=len(parsed.by_asin),
                prepared_row_count=len(asin_rows),
                preview_file_path=str(asin_preview_path),
            ),
        )
        return self._finalize_result(
            marketplace_id=marketplace_id,
            started_at=started_at,
            run_output_dir=run_output_dir,
            raw_file_path=str(path),
            report_start_date=report_start_date,
            report_end_date=report_end_date,
            schema_validation_status=str(
                schema_event.get("validation_status") or schema_result.status
            ),
            requires_review=False,
            table_results=table_results,
            schema_validation_event=schema_event,
            fail_on_review=fail_on_review,
        )

    def _build_missing_file_result(
        self,
        *,
        marketplace_id: str,
        started_at: str,
        run_output_dir: Path,
        skip_reason: str,
        raw_file_path: str | None = None,
    ) -> SalesTrafficIngestionDryRunResult:
        table_results = (
            SalesTrafficPreparedTableResult(
                report_type=SALES_AND_TRAFFIC_REPORT_TYPE,
                target_table=SALES_TRAFFIC_DAILY_TABLE_SPEC.target_table,
                raw_file_path=raw_file_path,
                schema_validation_status=None,
                requires_review=True,
                skipped=True,
                skip_reason=skip_reason,
                parsed_row_count=0,
                prepared_row_count=0,
                preview_file_path=None,
            ),
            SalesTrafficPreparedTableResult(
                report_type=SALES_AND_TRAFFIC_REPORT_TYPE,
                target_table=SALES_TRAFFIC_ASIN_TABLE_SPEC.target_table,
                raw_file_path=raw_file_path,
                schema_validation_status=None,
                requires_review=True,
                skipped=True,
                skip_reason=skip_reason,
                parsed_row_count=0,
                prepared_row_count=0,
                preview_file_path=None,
            ),
        )
        return self._finalize_result(
            marketplace_id=marketplace_id,
            started_at=started_at,
            run_output_dir=run_output_dir,
            raw_file_path=raw_file_path,
            report_start_date=None,
            report_end_date=None,
            schema_validation_status=None,
            requires_review=True,
            table_results=table_results,
            schema_validation_event=None,
            fail_on_review=True,
        )

    def _finalize_result(
        self,
        *,
        marketplace_id: str,
        started_at: str,
        run_output_dir: Path,
        raw_file_path: str | None,
        report_start_date: str | None,
        report_end_date: str | None,
        schema_validation_status: str | None,
        requires_review: bool,
        table_results: tuple[SalesTrafficPreparedTableResult, ...],
        schema_validation_event: dict[str, Any] | None,
        fail_on_review: bool,
    ) -> SalesTrafficIngestionDryRunResult:
        finished_at = _utc_now_iso()
        status = "requires_review" if requires_review else "success"
        if fail_on_review and requires_review:
            status = "failed_requires_review"
        task_audit_event = build_task_audit_event(
            marketplace_id=marketplace_id,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            output_dir=str(run_output_dir),
            raw_file_path=raw_file_path,
            report_start_date=report_start_date,
            report_end_date=report_end_date,
            table_results=table_results,
        )
        result = SalesTrafficIngestionDryRunResult(
            workflow_name="sp_api_sales_traffic_ingestion_dry_run",
            marketplace_id=marketplace_id,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            requires_review=requires_review,
            processed_file_count=1 if raw_file_path else 0,
            parsed_row_count=sum(item.parsed_row_count for item in table_results),
            prepared_row_count=sum(item.prepared_row_count for item in table_results),
            preview_file_count=sum(1 for item in table_results if item.preview_file_path),
            skipped_table_count=sum(1 for item in table_results if item.skipped),
            output_dir=str(run_output_dir),
            raw_file_path=raw_file_path,
            report_start_date=report_start_date,
            report_end_date=report_end_date,
            schema_validation_status=schema_validation_status,
            table_results=table_results,
            schema_validation_event=schema_validation_event,
            task_audit_event=task_audit_event,
        )
        _write_json(run_output_dir / "task_audit_event.json", task_audit_event)
        _write_json(run_output_dir / "sales_traffic_ingestion_summary.json", result.to_dict())
        return result

    def _build_run_output_dir(self, *, marketplace_id: str) -> Path:
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
        output_dir = (
            self.output_root
            / SALES_AND_TRAFFIC_REPORT_TYPE
            / _safe_path_part(marketplace_id)
            / timestamp
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir


def build_sales_traffic_expected_schema() -> ExpectedReportSchema:
    return ExpectedReportSchema(
        source_system="sp_api_reports",
        report_type=SALES_AND_TRAFFIC_REPORT_TYPE,
        expected_fields=SALES_TRAFFIC_DAILY_TABLE_SPEC.expected_fields,
        required_fields=SALES_TRAFFIC_DAILY_TABLE_SPEC.required_fields,
        allow_extra_fields=False,
        allow_empty_report=True,
        notes="Sales & Traffic JSON schema observed from GET_SALES_AND_TRAFFIC_REPORT.",
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
        path for pattern in ("*.txt", "*.json") for path in root.rglob(pattern) if path.is_file()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def build_task_audit_event(
    *,
    marketplace_id: str,
    started_at: str,
    finished_at: str,
    status: str,
    output_dir: str,
    raw_file_path: str | None,
    report_start_date: str | None,
    report_end_date: str | None,
    table_results: tuple[SalesTrafficPreparedTableResult, ...],
) -> dict[str, Any]:
    rows_read = sum(item.parsed_row_count for item in table_results)
    rows_written = sum(item.prepared_row_count for item in table_results)
    rows_skipped = sum(1 for item in table_results if item.skipped)
    files_created = sum(1 for item in table_results if item.preview_file_path) + 3
    return {
        "workflow_name": "sp_api_sales_traffic_ingestion_dry_run",
        "job_name": "prepare_sales_traffic_ingestion",
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
        "date_start": report_start_date,
        "date_end": report_end_date,
        "rows_read": rows_read,
        "rows_written": rows_written,
        "rows_skipped": rows_skipped,
        "rows_failed": 0,
        "files_created": files_created,
        "retry_count": 0,
        "config_snapshot_json": json.dumps(
            {
                "marketplace_id": marketplace_id,
                "output_dir": output_dir,
                "raw_file_path": raw_file_path,
                "report_type": SALES_AND_TRAFFIC_REPORT_TYPE,
                "target_tables": [item.target_table for item in table_results],
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        "message": _build_task_message(table_results),
        "error_type": None,
        "error_detail": None,
    }


def _validate_supported_report_options(report_specification: dict[str, Any]) -> str | None:
    report_options = report_specification.get("reportOptions")
    if not isinstance(report_options, dict):
        return "Sales & Traffic reportSpecification.reportOptions is missing or not an object."
    date_granularity = _empty_to_none(report_options.get("dateGranularity"))
    asin_granularity = _empty_to_none(report_options.get("asinGranularity"))
    if date_granularity != "DAY":
        return (
            "Unsupported Sales & Traffic dateGranularity. "
            f"Expected 'DAY' for the first implementation, got {date_granularity!r}."
        )
    if asin_granularity != "PARENT":
        return (
            "Unsupported Sales & Traffic asinGranularity. "
            f"Expected 'PARENT' for the first implementation, got {asin_granularity!r}."
        )
    return None


def _build_task_message(table_results: tuple[SalesTrafficPreparedTableResult, ...]) -> str:
    if any(item.requires_review for item in table_results):
        targets = [item.target_table for item in table_results if item.requires_review]
        return "Requires review: " + ", ".join(targets)
    prepared = [f"{item.target_table}={item.prepared_row_count}" for item in table_results]
    return "Prepared Sales & Traffic DB-ready preview rows: " + ", ".join(prepared)


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


def _empty_to_none(value: Any) -> str | None:
    if value is None:
        return None
    value_str = str(value).strip()
    return value_str or None


__all__ = [
    "SalesTrafficIngestionDryRunResult",
    "SalesTrafficIngestionDryRunService",
    "SalesTrafficPreparedTableResult",
    "build_sales_traffic_expected_schema",
    "build_task_audit_event",
    "find_latest_sp_api_raw_file",
]
