from __future__ import annotations

from datetime import date

from seller_data_pipeline.ingestion.listing_table_mapping import (
    LISTING_TARGET_TABLE_SPEC,
    map_listing_record_to_table_row,
)
from seller_data_pipeline.parsers.amazon.listings_all_data_parser import ListingsAllDataParser

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


def test_map_listing_record_to_table_row_is_db_ready() -> None:
    record = ListingsAllDataParser().parse_bytes(
        content=LISTING_CONTENT.encode("utf-8"),
        marketplace_id="ATVPDKIKX0DER",
        snapshot_date=date(2026, 5, 13),
        source_report_id="report-1",
        source_raw_file_path="reports/raw/report-1.txt",
    )[0]

    row = map_listing_record_to_table_row(record)

    assert tuple(row) == LISTING_TARGET_TABLE_SPEC.table_columns
    assert row["marketplace_id"] == "ATVPDKIKX0DER"
    assert row["snapshot_date"] == "2026-05-13"
    assert row["listing_id"] == "listing-1"
    assert row["seller_sku"] == "SKU-1"
    assert row["asin"] == "B000TEST01"
    assert row["price"] == "25.50"
    assert row["item_is_marketplace"] is True
    assert row["open_date_utc"] is None
    assert row["business_key_hash"]
    assert isinstance(row["raw_data"], str)
