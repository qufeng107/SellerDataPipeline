from __future__ import annotations

import json
from pathlib import Path

from seller_data_pipeline.ingestion.ads_ingestion_dry_run import AdsIngestionDryRunService


def _write_ads_raw(
    root: Path,
    profile_id: str,
    report_type_id: str,
    report_id: str,
    payload: str,
) -> Path:
    path = root / "amazon_ads" / profile_id / report_type_id / "2026-05-15" / f"{report_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return path


def test_ads_ingestion_dry_run_writes_preview_and_audit(tmp_path: Path) -> None:
    raw_root = tmp_path / "reports" / "raw"
    output_root = tmp_path / "runtime" / "ingestion" / "amazon_ads"
    _write_ads_raw(
        raw_root,
        "3917953989967300",
        "spCampaigns",
        "ads-report-1",
        (
            '[{"date":"2026-05-12","campaignId":123,"campaignName":"Campaign A",'
            '"campaignStatus":"ENABLED","impressions":10,"clicks":2,"cost":"1.23",'
            '"sales7d":"9.99","purchases7d":1,"unitsSoldClicks7d":1}]'
        ),
    )

    result = AdsIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=output_root,
    ).prepare(
        profile_id="3917953989967300",
        report_type_ids=["spCampaigns"],
        marketplace_id="ATVPDKIKX0DER",
    )

    assert result.status == "success"
    assert result.processed_file_count == 1
    assert result.prepared_row_count == 1
    assert result.preview_file_count == 1
    summary_path = Path(result.output_dir) / "ads_ingestion_summary.json"
    audit_path = Path(result.output_dir) / "task_audit_event.json"
    schema_events_path = Path(result.output_dir) / "schema_validation_events.jsonl"
    assert summary_path.exists()
    assert audit_path.exists()
    assert schema_events_path.exists()
    preview_path = Path(result.report_results[0].preview_file_path or "")
    preview_row = json.loads(preview_path.read_text(encoding="utf-8").splitlines()[0])
    assert preview_row["marketplace_id"] == "ATVPDKIKX0DER"
    assert preview_row["business_key_hash"]


def test_ads_ingestion_dry_run_blocks_schema_drift(tmp_path: Path) -> None:
    raw_root = tmp_path / "reports" / "raw"
    _write_ads_raw(
        raw_root,
        "3917953989967300",
        "spCampaigns",
        "ads-report-1",
        '[{"date":"2026-05-12","campaignId":123,"unexpectedMetric":1}]',
    )

    service = AdsIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=tmp_path / "out",
    )
    result = service.prepare(
        profile_id="3917953989967300",
        report_type_ids=["spCampaigns"],
    )

    assert result.status == "requires_review"
    assert result.requires_review is True
    assert result.report_results[0].skipped is True
    assert result.report_results[0].skip_reason == "schema_validation_requires_review"
    assert result.report_results[0].prepared_row_count == 0


def test_ads_ingestion_dry_run_skips_not_ready_mapping_without_review(tmp_path: Path) -> None:
    result = AdsIngestionDryRunService(
        raw_reports_root=tmp_path / "reports" / "raw",
        output_root=tmp_path / "out",
    ).prepare(
        profile_id="3917953989967300",
        report_type_ids=["spPurchasedProduct"],
    )

    assert result.status == "success"
    assert result.skipped_report_count == 1
    assert (
        result.report_results[0].skip_reason == "target_table_not_ready_non_empty_sample_required"
    )
    assert result.report_results[0].requires_review is False
