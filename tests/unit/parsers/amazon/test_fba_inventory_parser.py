from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

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


def test_fba_inventory_parser_maps_core_fields() -> None:
    records = FbaInventoryParser().parse_bytes(
        content=INVENTORY_CONTENT.encode("cp1252"),
        marketplace_id="ATVPDKIKX0DER",
        snapshot_date=date(2026, 5, 14),
        source_report_id="report-2",
        source_raw_file_path="reports/raw/report-2.txt",
    )

    assert len(records) == 1
    record = records[0]
    assert record.marketplace_id == "ATVPDKIKX0DER"
    assert record.snapshot_date == "2026-05-14"
    assert record.seller_sku == "SKU-1"
    assert record.fnsku == "FNSKU-1"
    assert record.asin == "B000TEST01"
    assert record.your_price == Decimal("26.00")
    assert record.mfn_listing_exists is False
    assert record.mfn_fulfillable_quantity is None
    assert record.afn_listing_exists is True
    assert record.afn_warehouse_quantity == 284
    assert record.afn_fulfillable_quantity == 277
    assert record.afn_unsellable_quantity == 1
    assert record.afn_reserved_quantity == 6
    assert record.afn_total_quantity == 284
    assert record.per_unit_volume == Decimal("0.03")
    assert record.store is None
    assert record.source_report_type == "GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA"
    assert len(record.source_row_hash) == 64
    assert record.to_dict()["your_price"] == "26.00"
    assert record.to_dict()["per_unit_volume"] == "0.03"


def test_fba_inventory_parser_rejects_missing_required_fields() -> None:
    with pytest.raises(ValueError, match="Missing required FBA inventory report fields"):
        FbaInventoryParser().parse_bytes(
            content=b"sku\tafn-fulfillable-quantity\nSKU-1\t1\n",
            marketplace_id="ATVPDKIKX0DER",
        )
