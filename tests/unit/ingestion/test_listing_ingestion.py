from __future__ import annotations

from seller_data_pipeline.db.repositories.listing_repo import (
    ListingUpsertRunResult,
    ListingUpsertTableResult,
)
from seller_data_pipeline.ingestion.listing_ingestion import build_final_audit_event


def test_build_final_audit_event_uses_listing_upsert_written_rows() -> None:
    class ReportResult:
        snapshot_date = "2026-05-13"

    class DryRun:
        parsed_row_count = 6
        report_result = ReportResult()
        task_audit_event = {
            "workflow_name": "sp_api_listing_ingestion_dry_run",
            "job_name": "prepare_listing_snapshot_ingestion",
            "rows_read": 6,
            "rows_written": 6,
        }

    upsert = ListingUpsertRunResult(
        table_result=ListingUpsertTableResult(
            table_name="amazon_listing_snapshot",
            report_type="GET_MERCHANT_LISTINGS_ALL_DATA",
            attempted_rows=6,
            inserted_rows=4,
            updated_rows=2,
            skipped_rows=0,
        ),
        sync_run_id=10,
    )

    event = build_final_audit_event(
        dry_run_result=DryRun(),  # type: ignore[arg-type]
        upsert_result=upsert,
        started_at="2026-05-16T21:00:00Z",
        status="success",
        message="done",
    )

    assert event["workflow_name"] == "sp_api_listing_ingestion"
    assert event["job_name"] == "ingest_listing_snapshot"
    assert event["rows_read"] == 6
    assert event["rows_written"] == 6
    assert event["rows_skipped"] == 0
    assert event["message"] == "done"
