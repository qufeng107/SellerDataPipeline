from __future__ import annotations

from seller_data_pipeline.ingestion.settlement_table_mapping import (
    SETTLEMENT_TARGET_TABLE_SPEC,
    map_settlement_record_to_table_row,
)
from seller_data_pipeline.parsers.amazon.settlement_report_parser import SettlementReportParser

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


def test_map_settlement_record_to_table_row_is_db_ready() -> None:
    record = SettlementReportParser().parse_bytes(
        content=SETTLEMENT_CONTENT.encode("cp1252"),
        marketplace_id="ATVPDKIKX0DER",
        source_report_id="settlement-report-1",
        source_raw_file_path="reports/raw/settlement-report-1.txt",
    )[1]

    row = map_settlement_record_to_table_row(record, source_row_index=2)

    assert tuple(row) == SETTLEMENT_TARGET_TABLE_SPEC.table_columns
    assert row["marketplace_id"] == "ATVPDKIKX0DER"
    assert row["settlement_id"] == "25829544191"
    assert row["transaction_type"] == "Order"
    assert row["order_id"] == "ORDER-1"
    assert row["seller_sku"] == "SKU-1"
    assert row["amount"] == "26.00"
    assert row["amount_category"] == "product_sales"
    assert row["profit_bucket"] == "revenue"
    assert row["source_row_index"] == 2
    assert row["business_key_hash"]
    assert isinstance(row["raw_data"], str)
