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
    preview_rows = [
        json.loads(line) for line in preview_path.read_text(encoding="utf-8").splitlines()
    ]
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


def test_settlement_ingestion_dry_run_quarantines_provably_foreign_currency_report(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "reports" / "raw"
    cad_payload = SETTLEMENT_CONTENT.replace("\tUSD\t", "\tCAD\t", 1)
    _write_settlement_raw(
        raw_root,
        "ATVPDKIKX0DER",
        "settlement-report-cad",
        cad_payload,
    )

    result = SettlementIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=tmp_path / "out",
    ).prepare(marketplace_id="ATVPDKIKX0DER")

    assert result.status == "success"
    assert result.requires_review is False
    assert result.prepared_row_count == 0
    assert result.file_results[0].skipped is True
    assert "foreign_marketplace_report" in str(result.file_results[0].skip_reason)
    assert "expects USD" in str(result.file_results[0].skip_reason)
    assert "CAD" in str(result.file_results[0].skip_reason)





def test_settlement_ingestion_continues_valid_us_files_when_foreign_report_is_quarantined(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "reports" / "raw"
    _write_settlement_raw(
        raw_root,
        "ATVPDKIKX0DER",
        "settlement-report-us",
        SETTLEMENT_CONTENT,
    )
    _write_settlement_raw(
        raw_root,
        "ATVPDKIKX0DER",
        "settlement-report-cad",
        SETTLEMENT_CONTENT.replace("\tUSD\t", "\tCAD\t", 1),
    )

    result = SettlementIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=tmp_path / "out",
    ).prepare(marketplace_id="ATVPDKIKX0DER")

    assert result.status == "success"
    assert result.requires_review is False
    assert result.processed_file_count == 2
    assert result.skipped_file_count == 1
    assert result.prepared_row_count == 2
    skipped = next(item for item in result.file_results if item.skipped)
    assert "foreign_marketplace_report" in str(skipped.skip_reason)

def test_settlement_ingestion_dry_run_blocks_mixed_currency_report(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "reports" / "raw"
    lines = SETTLEMENT_CONTENT.splitlines()
    # Add a second transaction row with an explicit CAD currency so the file is not
    # safely attributable to one foreign marketplace and must fail closed.
    fields = lines[-1].split("\t")
    currency_index = lines[0].split("\t").index("currency")
    fields[currency_index] = "CAD"
    mixed_payload = "\n".join(lines + ["\t".join(fields)]) + "\n"
    _write_settlement_raw(
        raw_root,
        "ATVPDKIKX0DER",
        "settlement-report-mixed-currency",
        mixed_payload,
    )

    result = SettlementIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=tmp_path / "out",
    ).prepare(marketplace_id="ATVPDKIKX0DER")

    assert result.status == "requires_review"
    assert result.requires_review is True
    assert result.prepared_row_count == 0
    assert "currencies=['CAD', 'USD']" in str(result.file_results[0].skip_reason)

def test_settlement_ingestion_dry_run_blocks_marketplace_name_mismatch_for_known_marketplace(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "reports" / "raw"
    foreign_marketplace_payload = SETTLEMENT_CONTENT.replace("Amazon.com", "Amazon.ca")
    _write_settlement_raw(
        raw_root,
        "ATVPDKIKX0DER",
        "settlement-report-marketplace-name-mismatch",
        foreign_marketplace_payload,
    )

    result = SettlementIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=tmp_path / "out",
    ).prepare(marketplace_id="ATVPDKIKX0DER")

    assert result.status == "requires_review"
    assert result.requires_review is True
    assert result.prepared_row_count == 0
    assert result.file_results[0].skipped is True
    assert "unexpected marketplace names" in str(result.file_results[0].skip_reason)
    assert "Amazon.ca" in str(result.file_results[0].skip_reason)

def test_settlement_ingestion_deduplicates_identical_report_id_across_collection_paths(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "reports" / "raw"
    first = _write_settlement_raw(
        raw_root,
        "ATVPDKIKX0DER",
        "same-report",
    )
    second = (
        raw_root
        / "amazon"
        / "ATVPDKIKX0DER"
        / "GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2"
        / "2026-08-05"
        / "same-report.txt"
    )
    second.parent.mkdir(parents=True, exist_ok=True)
    second.write_bytes(first.read_bytes())

    result = SettlementIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=tmp_path / "out",
    ).prepare(marketplace_id="ATVPDKIKX0DER")

    assert result.status == "success"
    assert result.processed_file_count == 1
    assert result.prepared_row_count == 2
    assert result.file_results[0].raw_file_path == str(second)


def test_settlement_ingestion_fails_closed_for_same_report_id_with_different_bytes(
    tmp_path: Path,
) -> None:
    import pytest

    raw_root = tmp_path / "reports" / "raw"
    first = _write_settlement_raw(
        raw_root,
        "ATVPDKIKX0DER",
        "same-report",
    )
    second = (
        raw_root
        / "amazon"
        / "ATVPDKIKX0DER"
        / "GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2"
        / "2026-08-05"
        / "same-report.txt"
    )
    second.parent.mkdir(parents=True, exist_ok=True)
    second.write_bytes(first.read_bytes() + b"\n")

    service = SettlementIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=tmp_path / "out",
    )
    with pytest.raises(ValueError, match="Conflicting Settlement raw files"):
        service.prepare(marketplace_id="ATVPDKIKX0DER")
