from __future__ import annotations

import json
from pathlib import Path

from seller_data_pipeline.ingestion.settlement_ingestion_dry_run import (
    SettlementIngestionDryRunService,
)

SETTLEMENT_CONTENT = (
    "settlement-id\tsettlement-start-date\tsettlement-end-date\tdeposit-date\ttotal-amount\t"
    "currency\ttransaction-type\torder-id\tmerchant-order-id\tadjustment-id\tshipment-id\t"
    "marketplace-name\tamount-type\tamount-description\tamount\tfulfillment-id\tposted-date\t"
    "posted-date-time\torder-item-code\tmerchant-order-item-id\tmerchant-adjustment-item-id\t"
    "sku\tquantity-purchased\tpromotion-id\n"
    "25829544191\t2026-03-06 08:52:26 UTC\t2026-03-20 08:52:26 UTC\t"
    "2026-03-22 08:52:26 UTC\t649.12\tUSD\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\n"
    "\t\t\t\t\t\tOrder\tORDER-1\t\t\tSHIP-1\tAmazon.com\tItemPrice\tPrincipal\t"
    "26.00\tAFN\t2026-03-07\t2026-03-07 10:00:00 UTC\tITEM-1\t\t\tSKU-1\t1\t\n"
)


def _write_settlement_raw(
    root: Path,
    marketplace_id: str,
    report_id: str,
    payload: str = SETTLEMENT_CONTENT,
) -> Path:
    path = (
        root
        / "amazon"
        / marketplace_id
        / "GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2"
        / "2026-05-14"
        / f"{report_id}.txt"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload.encode("cp1252"))
    return path


def test_settlement_ingestion_dry_run_writes_preview_and_audit(tmp_path: Path) -> None:
    raw_root = tmp_path / "reports" / "raw"
    output_root = tmp_path / "runtime" / "ingestion" / "sp_api"
    _write_settlement_raw(raw_root, "ATVPDKIKX0DER", "settlement-report-1")

    result = SettlementIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=output_root,
    ).prepare(marketplace_id="ATVPDKIKX0DER")

    assert result.status == "success"
    assert result.processed_file_count == 1
    assert result.prepared_row_count == 2
    assert result.preview_file_count == 1
    summary_path = Path(result.output_dir) / "settlement_ingestion_summary.json"
    audit_path = Path(result.output_dir) / "task_audit_event.json"
    schema_events_path = Path(result.output_dir) / "schema_validation_events.jsonl"
    assert summary_path.exists()
    assert audit_path.exists()
    assert schema_events_path.exists()
    preview_path = Path(result.preview_file_path or "")
    preview_rows = [json.loads(line) for line in preview_path.read_text(encoding="utf-8").splitlines()]
    assert len(preview_rows) == 2
    assert preview_rows[0]["is_settlement_summary"] is True
    assert preview_rows[1]["is_settlement_summary"] is False
    assert preview_rows[1]["business_key_hash"]
    assert preview_rows[1]["source_row_index"] == 2


def test_settlement_ingestion_dry_run_blocks_schema_drift(tmp_path: Path) -> None:
    raw_root = tmp_path / "reports" / "raw"
    _write_settlement_raw(
        raw_root,
        "ATVPDKIKX0DER",
        "settlement-report-1",
        "settlement-id\tunexpected\n25829544191\tvalue\n",
    )

    result = SettlementIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=tmp_path / "out",
    ).prepare(marketplace_id="ATVPDKIKX0DER")

    assert result.status == "requires_review"
    assert result.requires_review is True
    assert result.file_results[0].skipped is True
    assert result.file_results[0].skip_reason == "schema_validation_requires_review"
    assert result.prepared_row_count == 0
