from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

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


def test_listings_all_data_parser_maps_core_fields() -> None:
    records = ListingsAllDataParser().parse_bytes(
        content=LISTING_CONTENT.encode("utf-8"),
        marketplace_id="ATVPDKIKX0DER",
        snapshot_date=date(2026, 5, 13),
        source_report_id="report-1",
        source_raw_file_path="reports/raw/report-1.txt",
    )

    assert len(records) == 1
    record = records[0]
    assert record.marketplace_id == "ATVPDKIKX0DER"
    assert record.snapshot_date == "2026-05-13"
    assert record.listing_id == "listing-1"
    assert record.seller_sku == "SKU-1"
    assert record.asin == "B000TEST01"
    assert record.price == Decimal("25.50")
    assert record.quantity is None
    assert record.item_is_marketplace is True
    assert record.fulfillment_channel == "AMAZON_NA"
    assert record.source_report_type == "GET_MERCHANT_LISTINGS_ALL_DATA"
    assert len(record.source_row_hash) == 64
    assert record.to_dict()["price"] == "25.50"


def test_listings_all_data_parser_rejects_missing_required_fields() -> None:
    with pytest.raises(ValueError, match="Missing required listing report fields"):
        ListingsAllDataParser().parse_bytes(
            content=b"seller-sku\tprice\nSKU-1\t25\n",
            marketplace_id="ATVPDKIKX0DER",
        )
