from __future__ import annotations

from seller_data_pipeline.db.repositories.ads_repo import AdsUpsertRunResult, AdsUpsertTableResult
from seller_data_pipeline.ingestion.ads_ingestion import build_final_audit_event


def test_build_final_audit_event_uses_upsert_written_rows() -> None:
    class DryRun:
        parsed_row_count = 5
        task_audit_event = {
            "workflow_name": "amazon_ads_ingestion_dry_run",
            "job_name": "prepare_ads_ingestion",
            "rows_read": 5,
            "rows_written": 5,
        }

    upsert = AdsUpsertRunResult(
        table_results=(
            AdsUpsertTableResult(
                table_name="amazon_ads_sp_campaign_daily",
                report_type_id="spCampaigns",
                attempted_rows=5,
                inserted_rows=3,
                updated_rows=2,
                skipped_rows=0,
            ),
        ),
        sync_run_id=10,
    )

    event = build_final_audit_event(
        dry_run_result=DryRun(),  # type: ignore[arg-type]
        upsert_result=upsert,
        started_at="2026-05-15T21:00:00Z",
        status="success",
        message="done",
    )

    assert event["workflow_name"] == "amazon_ads_ingestion"
    assert event["job_name"] == "ingest_ads_reports"
    assert event["rows_read"] == 5
    assert event["rows_written"] == 5
    assert event["rows_skipped"] == 0
    assert event["message"] == "done"
