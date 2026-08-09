from __future__ import annotations

from seller_data_pipeline.parsers.amazon.settlement_report_parser import SettlementReportParser

HEADER = "\t".join(
    [
        "settlement-id",
        "settlement-start-date",
        "settlement-end-date",
        "deposit-date",
        "total-amount",
        "currency",
        "transaction-type",
        "order-id",
        "merchant-order-id",
        "adjustment-id",
        "shipment-id",
        "marketplace-name",
        "amount-type",
        "amount-description",
        "amount",
        "fulfillment-id",
        "posted-date",
        "posted-date-time",
        "order-item-code",
        "merchant-order-item-id",
        "merchant-adjustment-item-id",
        "sku",
        "quantity-purchased",
        "promotion-id",
    ]
)


def _row(values: list[str]) -> str:
    return "\t".join(values)


def test_parse_settlement_v2_report() -> None:
    content = (
        HEADER
        + "\n"
        + _row(
            [
                "123",
                "2026-05-01T00:00:00Z",
                "2026-05-14T00:00:00Z",
                "2026-05-16T00:00:00Z",
                "99.50",
                "USD",
                "Order",
                "111-2222222-3333333",
                "",
                "",
                "shipment-1",
                "Amazon.com",
                "ItemPrice",
                "Principal",
                "19.99",
                "AFN",
                "2026-05-10",
                "2026-05-10T12:00:00Z",
                "item-1",
                "",
                "",
                "SKU-1",
                "1",
                "",
            ]
        )
        + "\n"
    )

    records = SettlementReportParser().parse_text(
        text=content,
        marketplace_id="ATVPDKIKX0DER",
        source_report_id="report-1",
    )

    assert len(records) == 1
    record = records[0]
    assert record.marketplace_id == "ATVPDKIKX0DER"
    assert record.settlement_id == "123"
    assert str(record.total_amount) == "99.50"
    assert record.currency == "USD"
    assert record.transaction_type == "Order"
    assert record.amount_type == "ItemPrice"
    assert record.amount_description == "Principal"
    assert str(record.amount) == "19.99"
    assert record.amount_category == "product_sales"
    assert record.profit_bucket == "revenue"
    assert record.is_settlement_summary is False
    assert record.seller_sku == "SKU-1"
    assert record.quantity_purchased == 1
    assert record.source_report_type == "GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2"
    assert len(record.source_row_hash) == 64


def test_parse_settlement_decimal_with_comma_format() -> None:
    content = (
        HEADER
        + "\n"
        + _row(
            [
                "123",
                "",
                "",
                "",
                "1.234,56",
                "EUR",
                "Order",
                "order-1",
                "",
                "",
                "",
                "Amazon.de",
                "ItemFees",
                "Commission",
                "-2,50",
                "AFN",
                "",
                "",
                "",
                "",
                "",
                "SKU-1",
                "1",
                "",
            ]
        )
        + "\n"
    )

    record = SettlementReportParser().parse_text(text=content, marketplace_id="A1PA6795UKMFR9")[0]

    assert str(record.total_amount) == "1234.56"
    assert str(record.amount) == "-2.50"
    assert record.amount_category == "referral_fee"
    assert record.profit_bucket == "amazon_fee"


def test_settlement_summary_metadata_is_forward_filled_to_transaction_rows() -> None:
    content = (
        HEADER
        + "\n"
        + "\n".join(
            [
                _row(
                    [
                        "123",
                        "2026-05-01 00:00:00 UTC",
                        "2026-05-14 00:00:00 UTC",
                        "2026-05-16 00:00:00 UTC",
                        "99.50",
                        "USD",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]
                ),
                _row(
                    [
                        "123",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "Order",
                        "111-2222222-3333333",
                        "",
                        "",
                        "shipment-1",
                        "Amazon.com",
                        "ItemFees",
                        "FBAPerUnitFulfillmentFee",
                        "-4.06",
                        "AFN",
                        "2026-05-10",
                        "",
                        "item-1",
                        "",
                        "",
                        "SKU-1",
                        "1",
                        "",
                    ]
                ),
            ]
        )
        + "\n"
    )

    summary, transaction = SettlementReportParser().parse_text(
        text=content,
        marketplace_id="ATVPDKIKX0DER",
    )

    assert summary.is_settlement_summary is True
    assert summary.amount_category == "settlement_summary"
    assert summary.profit_bucket == "reconciliation"
    assert transaction.is_settlement_summary is False
    assert transaction.currency == "USD"
    assert transaction.settlement_start_date_raw == "2026-05-01 00:00:00 UTC"
    assert str(transaction.total_amount) == "99.50"
    assert transaction.amount_category == "fba_fulfillment_fee"
    assert transaction.profit_bucket == "fba_fee"
    assert transaction.raw_data["currency"] == ""


def test_classifies_advertiser_refund_as_advertising_cost() -> None:
    content = (
        HEADER
        + "\n"
        + _row(
            [
                "123",
                "2026-05-01T00:00:00Z",
                "2026-05-31T00:00:00Z",
                "2026-06-01T00:00:00Z",
                "0.00",
                "USD",
                "ServiceFee",
                "",
                "",
                "",
                "",
                "Amazon.com",
                "Refund for Advertiser",
                "TransactionTotalAmount",
                "500.08",
                "",
                "2026-05-30",
                "2026-05-30 10:00:00 UTC",
                "",
                "",
                "",
                "",
                "",
                "",
            ]
        )
        + "\n"
    )

    record = SettlementReportParser().parse_text(
        text=content,
        marketplace_id="ATVPDKIKX0DER",
        source_report_id="settlement-report-1",
    )[0]

    assert record.amount_category == "advertising_refund"
    assert record.profit_bucket == "advertising_cost"


def test_classifies_fba_inventory_storage_fee_from_amount_type() -> None:
    content = (
        HEADER
        + "\n"
        + _row(
            [
                "settlement-july",
                "2026-07-01T00:00:00Z",
                "2026-07-31T00:00:00Z",
                "2026-08-01T00:00:00Z",
                "0.00",
                "USD",
                "FBAFees",
                "",
                "",
                "",
                "",
                "Amazon.com",
                "FBA Inventory Storage Fee",
                "Base fee",
                "-32.75",
                "",
                "2026-07-31",
                "2026-07-31T12:00:00Z",
                "",
                "",
                "",
                "",
                "",
                "",
            ]
        )
        + "\n"
    )

    record = SettlementReportParser().parse_text(
        text=content,
        marketplace_id="ATVPDKIKX0DER",
        source_report_id="settlement-report-july-storage",
    )[0]

    assert record.amount_type == "FBA Inventory Storage Fee"
    assert record.amount_description == "Base fee"
    assert record.amount_category == "storage_fee"
    assert record.profit_bucket == "fba_storage_fee"


def test_classifies_fba_customer_returns_fee_with_dynamic_suffix() -> None:
    content = (
        HEADER
        + "\n"
        + _row(
            [
                "settlement-july",
                "2026-07-01T00:00:00Z",
                "2026-07-31T00:00:00Z",
                "2026-08-01T00:00:00Z",
                "0.00",
                "USD",
                "FBAFees",
                "",
                "",
                "",
                "",
                "Amazon.com",
                (
                    "FBA Customer Returns Fee (Non-Apparel and Non-Shoes) "
                    "for ASIN: B0G1YF2W1D (2026-04-01 to 2026-06-30)"
                ),
                "Base fee",
                "-2.70",
                "",
                "2026-07-31",
                "2026-07-31T12:00:00Z",
                "",
                "",
                "",
                "",
                "",
                "",
            ]
        )
        + "\n"
    )

    record = SettlementReportParser().parse_text(
        text=content,
        marketplace_id="ATVPDKIKX0DER",
        source_report_id="settlement-report-july-returns",
    )[0]

    assert record.amount_type.startswith("FBA Customer Returns Fee")
    assert record.amount_description == "Base fee"
    assert record.amount_category == "fba_customer_returns_fee"
    assert record.profit_bucket == "fba_fee"


def test_parse_settlement_raw_date_supports_iso_and_dd_dot_mm_dot_yyyy() -> None:
    from datetime import date

    from seller_data_pipeline.parsers.amazon.settlement_report_parser import (
        parse_settlement_raw_date,
    )

    assert parse_settlement_raw_date("2026-07-31 10:00:00 UTC") == date(2026, 7, 31)
    assert parse_settlement_raw_date("07.03.2026 16:48:30 UTC") == date(2026, 3, 7)


def test_parse_settlement_raw_date_rejects_unknown_nonempty_format() -> None:
    import pytest

    from seller_data_pipeline.parsers.amazon.settlement_report_parser import (
        parse_settlement_raw_date,
    )

    with pytest.raises(ValueError, match="Unsupported Settlement date format"):
        parse_settlement_raw_date("03/07/2026")
