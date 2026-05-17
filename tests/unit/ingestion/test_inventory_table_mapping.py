from __future__ import annotations

from datetime import date

from seller_data_pipeline.ingestion.inventory_table_mapping import (
    INVENTORY_TARGET_TABLE_SPEC,
    map_inventory_record_to_table_row,
)
from seller_data_pipeline.parsers.amazon.fba_inventory_parser import FbaInventoryParser

INVENTORY_CONTENT = (
    "sku\tfnsku\tasin\tproduct-name\tcondition\tyour-price\tmfn-listing-exists\t"
    "mfn-fulfillable-quantity\tafn-listing-exists\tafn-warehouse-quantity\t"
    "afn-fulfillable-quantity\tafn-unsellable-quantity\tafn-reserved-quantity\t"
    "afn-total-quantity\tper-unit-volume\tafn-inbound-working-quantity\t"
    "afn-inbound-shipped-quantity\tafn-inbound-receiving-quantity\t"
    "afn-researching-quantity\tafn-reserved-future-supply\t"
    "afn-future-supply-buyable\tstore\n"
    "SKU-1\tFNSKU-1\tB000TEST01\tTest Product\tNew\t26.00\tNo\t\tYes\t"
    "284\t277\t1\t6\t284\t0.03\t0\t0\t0\t0\t0\t0\t\n"
)


def test_map_inventory_record_to_table_row_is_db_ready() -> None:
    record = FbaInventoryParser().parse_bytes(
        content=INVENTORY_CONTENT.encode("cp1252"),
        marketplace_id="ATVPDKIKX0DER",
        snapshot_date=date(2026, 5, 14),
        source_report_id="report-2",
        source_raw_file_path="reports/raw/report-2.txt",
    )[0]

    row = map_inventory_record_to_table_row(record)

    assert tuple(row) == INVENTORY_TARGET_TABLE_SPEC.table_columns
    assert row["marketplace_id"] == "ATVPDKIKX0DER"
    assert row["snapshot_date"] == "2026-05-14"
    assert row["seller_sku"] == "SKU-1"
    assert row["fnsku"] == "FNSKU-1"
    assert row["asin"] == "B000TEST01"
    assert row["your_price"] == "26.00"
    assert row["mfn_listing_exists"] is False
    assert row["afn_listing_exists"] is True
    assert row["afn_fulfillable_quantity"] == 277
    assert row["business_key_hash"]
    assert isinstance(row["raw_data"], str)
