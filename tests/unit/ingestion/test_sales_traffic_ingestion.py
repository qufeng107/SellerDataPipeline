from __future__ import annotations

from seller_data_pipeline.db.repositories.sales_repo import (
    SalesTrafficUpsertRunResult,
    SalesTrafficUpsertTableResult,
)
from seller_data_pipeline.ingestion.sales_traffic_ingestion import (
    build_final_audit_event,
    build_running_audit_event,
)
from seller_data_pipeline.ingestion.sales_traffic_ingestion_dry_run import (
    SalesTrafficIngestionDryRunResult,
    SalesTrafficPreparedTableResult,
)


def _dry_run_result() -> SalesTrafficIngestionDryRunResult:
    daily = SalesTrafficPreparedTableResult(
        report_type="GET_SALES_AND_TRAFFIC_REPORT",
        target_table="amazon_sales_traffic_daily",
        raw_file_path="reports/raw/sales.txt",
        schema_validation_status="ok",
        requires_review=False,
        skipped=False,
        skip_reason=None,
        parsed_row_count=6,
        prepared_row_count=6,
        preview_file_path="runtime/daily.preview.jsonl",
    )
    asin = SalesTrafficPreparedTableResult(
        report_type="GET_SALES_AND_TRAFFIC_REPORT",
        target_table="amazon_sales_traffic_asin_daily",
        raw_file_path="reports/raw/sales.txt",
        schema_validation_status="ok",
        requires_review=False,
        skipped=False,
        skip_reason=None,
        parsed_row_count=1,
        prepared_row_count=1,
        preview_file_path="runtime/asin.preview.jsonl",
    )
    return SalesTrafficIngestionDryRunResult(
        workflow_name="sp_api_sales_traffic_ingestion_dry_run",
        marketplace_id="ATVPDKIKX0DER",
        started_at="2026-05-17T21:00:00Z",
        finished_at="2026-05-17T21:00:01Z",
        status="success",
        requires_review=False,
        processed_file_count=1,
        parsed_row_count=7,
        prepared_row_count=7,
        preview_file_count=2,
        skipped_table_count=0,
        output_dir="runtime/out",
        raw_file_path="reports/raw/sales.txt",
        report_start_date="2026-05-07",
        report_end_date="2026-05-14",
        schema_validation_status="ok",
        table_results=(daily, asin),
        schema_validation_event={"validation_status": "ok"},
        task_audit_event={
            "workflow_name": "sp_api_sales_traffic_ingestion_dry_run",
            "job_name": "prepare_sales_traffic_ingestion",
            "task_type": "ingestion_dry_run",
            "trigger_type": "manual",
            "run_mode": "local_dry_run",
            "marketplace_id": "ATVPDKIKX0DER",
            "source_system": "sp_api_reports",
            "status": "success",
            "started_at": "2026-05-17T21:00:00Z",
            "finished_at": "2026-05-17T21:00:01Z",
            "duration_ms": 1000,
            "date_start": "2026-05-07",
            "date_end": "2026-05-14",
            "rows_read": 7,
            "rows_written": 7,
            "rows_skipped": 0,
            "rows_failed": 0,
            "files_created": 5,
            "retry_count": 0,
            "config_snapshot_json": "{}",
            "message": "Prepared Sales & Traffic DB-ready preview rows",
            "error_type": None,
            "error_detail": None,
        },
    )


def test_build_running_audit_event_marks_sales_traffic_upsert() -> None:
    event = build_running_audit_event(
        dry_run_result=_dry_run_result(),
        started_at="2026-05-17T21:00:02Z",
    )

    assert event["workflow_name"] == "sp_api_sales_traffic_ingestion"
    assert event["job_name"] == "ingest_sales_traffic_report"
    assert event["run_mode"] == "azure_sql_write"
    assert event["status"] == "running"
    assert event["rows_written"] == 0


def test_build_final_audit_event_uses_aggregate_upsert_counts() -> None:
    daily = SalesTrafficUpsertTableResult(
        table_name="amazon_sales_traffic_daily",
        report_type="GET_SALES_AND_TRAFFIC_REPORT",
        attempted_rows=6,
        inserted_rows=4,
        updated_rows=2,
        skipped_rows=0,
    )
    asin = SalesTrafficUpsertTableResult(
        table_name="amazon_sales_traffic_asin_daily",
        report_type="GET_SALES_AND_TRAFFIC_REPORT",
        attempted_rows=1,
        inserted_rows=1,
        updated_rows=0,
        skipped_rows=0,
    )
    upsert_result = SalesTrafficUpsertRunResult(table_results=(daily, asin), sync_run_id=9)

    event = build_final_audit_event(
        dry_run_result=_dry_run_result(),
        upsert_result=upsert_result,
        started_at="2026-05-17T21:00:02Z",
        status="success",
        message="done",
    )

    assert event["rows_read"] == 7
    assert event["rows_written"] == 7
    assert event["rows_skipped"] == 0
    assert event["rows_failed"] == 0
    assert event["message"] == "done"
