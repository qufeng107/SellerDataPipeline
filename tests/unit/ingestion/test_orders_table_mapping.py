from __future__ import annotations

from seller_data_pipeline.ingestion.orders_table_mapping import (
    ORDERS_TARGET_TABLE_SPEC,
    map_orders_record_to_table_row,
)
from seller_data_pipeline.parsers.amazon.orders_report_parser import AllOrdersReportParser

ORDERS_CONTENT = (
    "amazon-order-id\tmerchant-order-id\tpurchase-date\tlast-updated-date\torder-status\t"
    "fulfillment-channel\tsales-channel\torder-channel\tship-service-level\tproduct-name\t"
    "sku\tasin\titem-status\tquantity\tcurrency\titem-price\titem-tax\tshipping-price\t"
    "shipping-tax\tgift-wrap-price\tgift-wrap-tax\titem-promotion-discount\t"
    "ship-promotion-discount\tship-city\tship-state\tship-postal-code\tship-country\t"
    "promotion-ids\tcpf\tis-business-order\tpurchase-order-number\tprice-designation\t"
    "signature-confirmation-recommended\n"
    "ORDER-1\tMERCHANT-1\t2026-05-08T23:36:26+00:00\t2026-05-09T01:00:00+00:00\t"
    "Shipped\tAmazon\tAmazon.com\t\tStandard\tTravel Wallet\tSKU-1\tB000TEST\tShipped\t2\t"
    "USD\t20.00\t1.20\t4.99\t0.30\t\t\t-2.00\t0.00\tReading\tCA\t90001\tUS\t"
    "PROMO-1\t\tfalse\t\t\tfalse\n"
)


def test_map_orders_record_to_table_row_is_db_ready() -> None:
    record = AllOrdersReportParser().parse_bytes(
        content=ORDERS_CONTENT.encode("utf-8"),
        marketplace_id="ATVPDKIKX0DER",
        source_report_id="orders-report-1",
        source_raw_file_path="reports/raw/orders-report-1.txt",
    )[0]

    row = map_orders_record_to_table_row(record, source_row_index=1)

    assert tuple(row) == ORDERS_TARGET_TABLE_SPEC.table_columns
    assert row["marketplace_id"] == "ATVPDKIKX0DER"
    assert row["amazon_order_id"] == "ORDER-1"
    assert row["seller_sku"] == "SKU-1"
    assert row["asin"] == "B000TEST"
    assert row["quantity"] == 2
    assert row["item_price"] == "20.00"
    assert row["item_promotion_discount"] == "-2.00"
    assert row["is_business_order"] is False
    assert row["source_row_index"] == 1
    assert row["business_key_hash"]
    assert isinstance(row["raw_data"], str)
