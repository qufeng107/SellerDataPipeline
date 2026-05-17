from __future__ import annotations

from pathlib import Path

from seller_data_pipeline.ingestion.inventory_ledger_ingestion_dry_run import (
    InventoryLedgerIngestionDryRunService,
)
from seller_data_pipeline.parsers.amazon.inventory_ledger_parser import (
    LEDGER_DETAIL_REPORT_TYPE,
    LEDGER_SUMMARY_REPORT_TYPE,
)

MARKETPLACE_ID = "ATVPDKIKX0DER"

SUMMARY_HEADER = [
    "Date",
    "FNSKU",
    "ASIN",
    "MSKU",
    "Title",
    "Disposition",
    "Starting Warehouse Balance",
    "In Transit Between Warehouses",
    "Receipts",
    "Customer Shipments",
    "Customer Returns",
    "Vendor Returns",
    "Warehouse Transfer In/Out",
    "Found",
    "Lost",
    "Damaged",
    "Disposed",
    "Other Events",
    "Ending Warehouse Balance",
    "Unknown Events",
    "Location",
    "Store",
]

DETAIL_HEADER = [
    "Date",
    "FNSKU",
    "ASIN",
    "MSKU",
    "Title",
    "Disposition",
    "Event Type",
    "Reference ID",
    "Quantity",
    "Fulfillment Center",
    "Reason",
    "Country",
    "Reconciled Quantity",
    "Unreconciled Quantity",
    "Date and Time",
    "Store",
]


def test_inventory_ledger_dry_run_uses_latest_valid_raw_files(tmp_path: Path) -> None:
    raw_root = tmp_path / "reports" / "raw"
    _write_ledger_summary_raw(raw_root, report_id="summary-1")
    _write_ledger_detail_raw(raw_root, report_id="detail-1")

    service = InventoryLedgerIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=tmp_path / "runtime",
    )
    result = service.prepare(marketplace_id=MARKETPLACE_ID)

    assert result.status == "success"
    assert result.requires_review is False
    assert result.prepared_row_count == 3
    assert result.preview_file_count == 2
    table_counts: dict[str, int] = {}
    for report_result in result.report_results:
        table_counts.update(report_result.table_row_counts)
    assert table_counts["amazon_inventory_ledger_summary_daily"] == 2
    assert table_counts["amazon_inventory_ledger_detail"] == 1


def _write_ledger_summary_raw(root: Path, *, report_id: str) -> Path:
    rows = [
        [
            "2026-05-01",
            "FNSKU-1",
            "ASIN-1",
            "SKU-1",
            "Product 1",
            "SELLABLE",
            "10",
            "0",
            "5",
            "2",
            "1",
            "0",
            "0",
            "0",
            "0",
            "0",
            "0",
            "0",
            "14",
            "0",
            "US",
            "Test Store",
        ],
        [
            "2026-05-02",
            "FNSKU-1",
            "ASIN-1",
            "SKU-1",
            "Product 1",
            "SELLABLE",
            "14",
            "0",
            "0",
            "1",
            "0",
            "0",
            "0",
            "0",
            "0",
            "0",
            "0",
            "0",
            "13",
            "0",
            "US",
            "Test Store",
        ],
    ]
    return _write_tsv(root, LEDGER_SUMMARY_REPORT_TYPE, report_id, SUMMARY_HEADER, rows)


def _write_ledger_detail_raw(root: Path, *, report_id: str) -> Path:
    rows = [
        [
            "2026-05-02",
            "FNSKU-1",
            "ASIN-1",
            "SKU-1",
            "Product 1",
            "SELLABLE",
            "Customer Shipments",
            "ORDER-1",
            "-1",
            "ABE8",
            "Order shipped",
            "US",
            "0",
            "0",
            "2026-05-02T12:00:00Z",
            "Test Store",
        ],
    ]
    return _write_tsv(root, LEDGER_DETAIL_REPORT_TYPE, report_id, DETAIL_HEADER, rows)


def _write_tsv(
    root: Path,
    report_type: str,
    report_id: str,
    header: list[str],
    rows: list[list[str]],
) -> Path:
    path = root / "amazon" / MARKETPLACE_ID / report_type / "2026-05-14" / f"{report_id}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    content = ["\t".join(header), *("\t".join(row) for row in rows)]
    path.write_text("\n".join(content) + "\n", encoding="utf-8")
    return path
