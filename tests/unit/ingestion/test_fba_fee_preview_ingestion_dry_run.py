from __future__ import annotations

import json
from pathlib import Path

from seller_data_pipeline.ingestion.fba_fee_preview_ingestion_dry_run import (
    FbaFeePreviewIngestionDryRunService,
)

FBA_FEE_PREVIEW_CONTENT = (
    "sku\tfnsku\tasin\tamazon-store\tproduct-name\tproduct-group\tbrand\tfulfilled-by\t"
    "your-price\tsales-price\tlongest-side\tmedian-side\tshortest-side\tlength-and-girth\t"
    "unit-of-dimension\titem-package-weight\tunit-of-weight\tproduct-size-tier\tcurrency\t"
    "estimated-fee-total\testimated-referral-fee-per-unit\testimated-variable-closing-fee\t"
    "estimated-order-handling-fee-per-order\testimated-pick-pack-fee-per-unit\t"
    "estimated-weight-handling-fee-per-unit\texpected-fulfillment-fee-per-unit\t"
    "estimated-future-fee (Current Selling on Amazon + Future Fulfillment fees)\t"
    "estimated-future-order-handling-fee-per-order\testimated-future-pick-pack-fee-per-unit\t"
    "estimated-future-weight-handling-fee-per-unit\texpected-future-fulfillment-fee-per-unit\n"
    "SKU-1\tFNSKU-1\tB000TEST\tUS\tTravel Wallet\tLuggage\tChynotopia\tAmazon\t"
    "25.00\t25.00\t7.72\t6.54\t1.22\t23.24\tinches\t0.18\tpounds\t"
    "UsLargeStandardSize\tUSD\t7.80\t3.75\t0.00\t--\t--\t--\t4.05\t--\t--\t--\t--\t--\n"
)


def _write_fba_fee_preview_raw(
    root: Path,
    marketplace_id: str,
    report_id: str,
    payload: str = FBA_FEE_PREVIEW_CONTENT,
) -> Path:
    path = (
        root
        / "amazon"
        / marketplace_id
        / "GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA"
        / "2026-05-14"
        / f"{report_id}.txt"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return path


def test_fba_fee_preview_ingestion_dry_run_writes_preview_and_audit(tmp_path: Path) -> None:
    raw_root = tmp_path / "reports" / "raw"
    output_root = tmp_path / "runtime" / "ingestion" / "sp_api"
    _write_fba_fee_preview_raw(raw_root, "ATVPDKIKX0DER", "fba-fee-preview-report-1")

    result = FbaFeePreviewIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=output_root,
    ).prepare(marketplace_id="ATVPDKIKX0DER")

    assert result.status == "success"
    assert result.processed_file_count == 1
    assert result.prepared_row_count == 1
    assert result.preview_file_count == 1
    summary_path = Path(result.output_dir) / "fba_fee_preview_ingestion_summary.json"
    audit_path = Path(result.output_dir) / "task_audit_event.json"
    schema_events_path = Path(result.output_dir) / "schema_validation_events.jsonl"
    assert summary_path.exists()
    assert audit_path.exists()
    assert schema_events_path.exists()
    preview_path = Path(result.report_result.preview_file_path or "")
    preview_rows = [
        json.loads(line)
        for line in preview_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(preview_rows) == 1
    assert preview_rows[0]["seller_sku"] == "SKU-1"
    assert preview_rows[0]["amazon_store"] == "US"
    assert preview_rows[0]["business_key_hash"]
    assert preview_rows[0]["source_row_index"] == 1


def test_fba_fee_preview_ingestion_dry_run_blocks_schema_drift(tmp_path: Path) -> None:
    raw_root = tmp_path / "reports" / "raw"
    _write_fba_fee_preview_raw(
        raw_root,
        "ATVPDKIKX0DER",
        "fba-fee-preview-report-1",
        "sku\tunexpected\nSKU-1\tvalue\n",
    )

    result = FbaFeePreviewIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=tmp_path / "out",
    ).prepare(marketplace_id="ATVPDKIKX0DER")

    assert result.status == "requires_review"
    assert result.requires_review is True
    assert result.report_result.skipped is True
    assert result.report_result.skip_reason == "schema_validation_requires_review"
    assert result.prepared_row_count == 0
