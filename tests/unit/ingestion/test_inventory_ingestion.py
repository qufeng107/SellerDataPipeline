from __future__ import annotations

from datetime import date

from seller_data_pipeline.db.repositories.inventory_repo import (
    InventoryUpsertRunResult,
    InventoryUpsertTableResult,
)
from seller_data_pipeline.ingestion.inventory_ingestion import (
    build_final_audit_event,
    build_running_audit_event,
)
from seller_data_pipeline.ingestion.inventory_ingestion_dry_run import (
    InventoryIngestionDryRunResult,
    InventoryPreparedReportResult,
)


def _dry_run_result() -> InventoryIngestionDryRunResult:
    prepared = InventoryPreparedReportResult(
        report_type="GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA",
        target_table="amazon_inventory_daily",
        raw_file_path="reports/raw/inventory.txt",
        snapshot_date="2026-05-14",
        schema_validation_status="ok",
        requires_review=False,
        skipped=False,
        skip_reason=None,
        parsed_row_count=5,
        prepared_row_count=5,
        preview_file_path="runtime/preview.jsonl",
        schema_validation_event={"validation_status": "ok"},
    )
    return InventoryIngestionDryRunResult(
        workflow_name="sp_api_inventory_ingestion_dry_run",
        marketplace_id="ATVPDKIKX0DER",
        started_at="2026-05-17T21:00:00Z",
        finished_at="2026-05-17T21:00:01Z",
        status="success",
        requires_review=False,
        processed_file_count=1,
        parsed_row_count=5,
        prepared_row_count=5,
        preview_file_count=1,
        skipped_report_count=0,
        output_dir="runtime/out",
        report_result=prepared,
        task_audit_event={
            "workflow_name": "sp_api_inventory_ingestion_dry_run",
            "job_name": "prepare_inventory_snapshot_ingestion",
            "task_type": "ingestion_dry_run",
            "trigger_type": "manual",
            "run_mode": "local_dry_run",
            "marketplace_id": "ATVPDKIKX0DER",
            "source_system": "sp_api_reports",
            "status": "success",
            "started_at": "2026-05-17T21:00:00Z",
            "finished_at": "2026-05-17T21:00:01Z",
            "duration_ms": 1000,
            "date_start": date(2026, 5, 14).isoformat(),
            "date_end": date(2026, 5, 14).isoformat(),
            "rows_read": 5,
            "rows_written": 5,
            "rows_skipped": 0,
            "rows_failed": 0,
            "files_created": 4,
            "retry_count": 0,
            "config_snapshot_json": "{}",
            "message": "Prepared Inventory DB-ready preview rows: 5",
            "error_type": None,
            "error_detail": None,
        },
    )


def test_build_running_audit_event_marks_inventory_upsert() -> None:
    event = build_running_audit_event(
        dry_run_result=_dry_run_result(),
        started_at="2026-05-17T21:00:02Z",
    )

    assert event["workflow_name"] == "sp_api_inventory_ingestion"
    assert event["job_name"] == "ingest_inventory_snapshot"
    assert event["run_mode"] == "azure_sql_write"
    assert event["status"] == "running"
    assert event["rows_written"] == 0


def test_build_final_audit_event_uses_upsert_counts() -> None:
    table_result = InventoryUpsertTableResult(
        table_name="amazon_inventory_daily",
        report_type="GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA",
        attempted_rows=5,
        inserted_rows=2,
        updated_rows=3,
        skipped_rows=0,
    )
    upsert_result = InventoryUpsertRunResult(table_result=table_result, sync_run_id=9)

    event = build_final_audit_event(
        dry_run_result=_dry_run_result(),
        upsert_result=upsert_result,
        started_at="2026-05-17T21:00:02Z",
        status="success",
        message="done",
    )

    assert event["rows_read"] == 5
    assert event["rows_written"] == 5
    assert event["rows_skipped"] == 0
    assert event["rows_failed"] == 0
    assert event["message"] == "done"
