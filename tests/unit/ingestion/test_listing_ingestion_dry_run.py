from __future__ import annotations

import json
from pathlib import Path

from seller_data_pipeline.ingestion.listing_ingestion_dry_run import (
    ListingIngestionDryRunService,
    infer_snapshot_date_from_path,
)

LISTING_CONTENT = (
    "item-name\titem-description\tlisting-id\tseller-sku\tprice\tquantity\topen-date\t"
    "image-url\titem-is-marketplace\tproduct-id-type\tzshop-shipping-fee\titem-note\t"
    "item-condition\tzshop-category1\tzshop-browse-path\tzshop-storefront-feature\t"
    "asin1\tasin2\tasin3\twill-ship-internationally\texpedited-shipping\t"
    "zshop-boldface\tproduct-id\tbid-for-featured-placement\tadd-delete\t"
    "pending-quantity\tfulfillment-channel\tmerchant-shipping-group\tstatus\n"
    "Test Product\tDescription\tlisting-1\tSKU-1\t25.50\t\t2026-05-01 00:00:00 PST\t"
    "\ty\t1\t\t\t11\t\t\t\tB000TEST01\t\t\t\t\t\tB000TEST01\t\t\t\t"
    "AMAZON_NA\tTemplate\tActive\n"
)


def _write_listing_raw(
    root: Path,
    marketplace_id: str,
    report_id: str,
    payload: str = LISTING_CONTENT,
) -> Path:
    path = (
        root
        / "amazon"
        / marketplace_id
        / "GET_MERCHANT_LISTINGS_ALL_DATA"
        / "2026-05-13"
        / f"{report_id}.txt"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return path


def test_listing_ingestion_dry_run_writes_preview_and_audit(tmp_path: Path) -> None:
    raw_root = tmp_path / "reports" / "raw"
    output_root = tmp_path / "runtime" / "ingestion" / "sp_api"
    _write_listing_raw(raw_root, "ATVPDKIKX0DER", "listing-report-1")

    result = ListingIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=output_root,
    ).prepare(marketplace_id="ATVPDKIKX0DER")

    assert result.status == "success"
    assert result.processed_file_count == 1
    assert result.prepared_row_count == 1
    assert result.preview_file_count == 1
    assert result.report_result.snapshot_date == "2026-05-13"
    summary_path = Path(result.output_dir) / "listing_ingestion_summary.json"
    audit_path = Path(result.output_dir) / "task_audit_event.json"
    schema_events_path = Path(result.output_dir) / "schema_validation_events.jsonl"
    assert summary_path.exists()
    assert audit_path.exists()
    assert schema_events_path.exists()
    preview_path = Path(result.report_result.preview_file_path or "")
    preview_row = json.loads(preview_path.read_text(encoding="utf-8").splitlines()[0])
    assert preview_row["marketplace_id"] == "ATVPDKIKX0DER"
    assert preview_row["snapshot_date"] == "2026-05-13"
    assert preview_row["business_key_hash"]


def test_listing_ingestion_dry_run_blocks_schema_drift(tmp_path: Path) -> None:
    raw_root = tmp_path / "reports" / "raw"
    _write_listing_raw(
        raw_root,
        "ATVPDKIKX0DER",
        "listing-report-1",
        "seller-sku\tunexpected\nSKU-1\tvalue\n",
    )

    result = ListingIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=tmp_path / "out",
    ).prepare(marketplace_id="ATVPDKIKX0DER")

    assert result.status == "requires_review"
    assert result.requires_review is True
    assert result.report_result.skipped is True
    assert result.report_result.skip_reason == "schema_validation_requires_review"
    assert result.report_result.prepared_row_count == 0


def test_infer_snapshot_date_from_path_uses_date_directory(tmp_path: Path) -> None:
    path = tmp_path / "amazon" / "ATVPDKIKX0DER" / "report" / "2026-05-13" / "1.txt"
    assert infer_snapshot_date_from_path(path).isoformat() == "2026-05-13"
