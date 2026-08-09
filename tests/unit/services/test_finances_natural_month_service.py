from __future__ import annotations

from datetime import date
from decimal import Decimal

from seller_data_pipeline.services.finances_natural_month_service import (
    prepare_natural_month_transactions,
)


def _tx(
    txid: str,
    *,
    status: str,
    typ: str,
    posted: str,
    amount: str,
    breakdowns=None,
    items=None,
):
    return {
        "transactionId": txid,
        "transactionStatus": status,
        "transactionType": typ,
        "postedDate": posted,
        "totalAmount": {"currencyCode": "USD", "currencyAmount": amount},
        "relatedIdentifiers": [
            {"relatedIdentifierName": "SETTLEMENT_ID", "relatedIdentifierValue": "S1"}
        ],
        "breakdowns": breakdowns or [],
        "items": items or [],
    }


def _shipment_breakdowns(product: str):
    return [
        {
            "breakdownType": "Sales",
            "breakdowns": [
                {
                    "breakdownType": "ProductCharges",
                    "breakdownAmount": {"currencyCode": "USD", "currencyAmount": product},
                }
            ],
        }
    ]


def test_us_natural_month_filters_utc_boundary_and_lifecycle_roles() -> None:
    transactions = [
        _tx(
            "boundary-june",
            status="DEFERRED_RELEASED",
            typ="Shipment",
            posted="2026-07-01T06:30:00Z",  # Jun 30 23:30 PDT
            amount="35.90",
            breakdowns=_shipment_breakdowns("52.00"),
        ),
        _tx(
            "july-order",
            status="DEFERRED_RELEASED",
            typ="Shipment",
            posted="2026-07-01T08:00:00Z",
            amount="100.00",
            breakdowns=_shipment_breakdowns("120.00"),
            items=[
                {
                    "contexts": [
                        {"contextType": "ProductContext", "sku": "SKU-1", "quantityShipped": 2}
                    ]
                }
            ],
        ),
        _tx(
            "old-order-release",
            status="RELEASED",
            typ="Shipment",
            posted="2026-07-10T12:00:00Z",
            amount="90.00",
        ),
        _tx(
            "july-refund",
            status="RELEASED",
            typ="Refund",
            posted="2026-07-11T12:00:00Z",
            amount="-20.00",
        ),
        _tx(
            "old-refund-release",
            status="DEFERRED_RELEASED",
            typ="Refund",
            posted="2026-07-12T12:00:00Z",
            amount="-30.00",
        ),
        _tx(
            "liq-deferred",
            status="DEFERRED",
            typ="RemovalShipment",
            posted="2026-07-13T12:00:00Z",
            amount="1.77",
            items=[{"contexts": [{"sku": "SKU-1", "quantityShipped": 1}]}],
        ),
        _tx(
            "liq-released",
            status="RELEASED",
            typ="RemovalShipment",
            posted="2026-07-14T12:00:00Z",
            amount="0.70",
        ),
        _tx(
            "service",
            status="RELEASED",
            typ="ServiceFee",
            posted="2026-07-15T12:00:00Z",
            amount="-5.00",
        ),
        _tx(
            "ads",
            status="RELEASED",
            typ="ProductAdsPayment",
            posted="2026-07-16T12:00:00Z",
            amount="-40.00",
        ),
        _tx(
            "transfer",
            status="RELEASED",
            typ="Transfer",
            posted="2026-07-17T12:00:00Z",
            amount="500.00",
        ),
    ]

    prepared = prepare_natural_month_transactions(
        transactions,
        marketplace_id="ATVPDKIKX0DER",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 31),
    )

    assert prepared.timezone_name == "America/Los_Angeles"
    assert prepared.local_transaction_count == 9
    assert prepared.review_required_count == 0
    summary = prepared.compact_summary()
    assert summary["management_operating_before_ads_replacement"] == "76.77"
    assert summary["finances_ads_charge_reference"] == "-40.00"
    assert summary["transfer_reference"] == "500.00"
    assert summary["product_sales_amount"] == "120.00"
    assert summary["management_unit_count"] == 3

    rows = {row.transaction_id: row for row in prepared.rows}
    assert rows["july-order"].management_include is True
    assert rows["old-order-release"].management_include is False
    assert rows["old-refund-release"].management_include is False
    assert rows["liq-released"].management_include is False
    assert rows["ads"].management_replace_with_ads_api is True


def test_unknown_nonzero_finance_transaction_requires_review() -> None:
    prepared = prepare_natural_month_transactions(
        [
            _tx(
                "new-type",
                status="RELEASED",
                typ="FutureAmazonType",
                posted="2026-07-10T12:00:00Z",
                amount="12.34",
            )
        ],
        marketplace_id="ATVPDKIKX0DER",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 31),
    )
    assert prepared.review_required_count == 1
    assert prepared.review_required_amount == Decimal("12.34")
    assert prepared.rows[0].management_include is False


def test_service_fee_components_are_preserved_for_management_reporting() -> None:
    prepared = prepare_natural_month_transactions(
        [
            _tx(
                "service-components",
                status="RELEASED",
                typ="ServiceFee",
                posted="2026-07-15T12:00:00Z",
                amount="-58.50",
                breakdowns=[
                    {
                        "breakdownType": "Expenses",
                        "breakdowns": [
                            {
                                "breakdownType": "SubscriptionFee",
                                "breakdownAmount": {
                                    "currencyCode": "USD",
                                    "currencyAmount": "-39.99",
                                },
                            },
                            {
                                "breakdownType": "CouponPerformanceFeeRollup",
                                "breakdownAmount": {
                                    "currencyCode": "USD",
                                    "currencyAmount": "-10.00",
                                },
                            },
                            {
                                "breakdownType": "StorageBillingFee",
                                "breakdownAmount": {
                                    "currencyCode": "USD",
                                    "currencyAmount": "-8.00",
                                },
                            },
                            {
                                "breakdownType": "OtherAccountFee",
                                "breakdownAmount": {
                                    "currencyCode": "USD",
                                    "currencyAmount": "-0.51",
                                },
                            },
                        ],
                    }
                ],
            )
        ],
        marketplace_id="ATVPDKIKX0DER",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 31),
    )

    row = prepared.rows[0]
    assert row.subscription_fee == Decimal("-39.99")
    assert row.coupon_fee == Decimal("-10.00")
    assert row.deal_fee == Decimal("0")
    assert row.storage_fee == Decimal("-8.00")
    assert row.customer_return_fee == Decimal("0")
    assert row.other_service_fee == Decimal("-0.51")


def test_included_unit_transaction_with_incomplete_item_context_requires_review() -> None:
    prepared = prepare_natural_month_transactions(
        [
            _tx(
                "missing-unit-context",
                status="DEFERRED_RELEASED",
                typ="Shipment",
                posted="2026-07-20T12:00:00Z",
                amount="20.00",
                breakdowns=_shipment_breakdowns("25.00"),
                items=[{"contexts": [{"asin": "B000TEST"}]}],
            )
        ],
        marketplace_id="ATVPDKIKX0DER",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 31),
    )

    assert prepared.review_required_count == 1
    assert prepared.rows[0].management_include is True
    assert prepared.rows[0].unit_events == ()
    assert any("unit-event coverage incomplete" in warning for warning in prepared.warnings)


def test_zero_value_released_shipment_is_cogs_only_unit_reference() -> None:
    prepared = prepare_natural_month_transactions(
        [
            _tx(
                "zero-value-order",
                status="RELEASED",
                typ="Shipment",
                posted="2026-06-03T19:13:19Z",
                amount="0.00",
                breakdowns=_shipment_breakdowns("0.00"),
                items=[
                    {
                        "contexts": [
                            {
                                "contextType": "ProductContext",
                                "sku": "SKU-ZERO",
                                "asin": "B000ZERO",
                                "quantityShipped": 1,
                            }
                        ]
                    }
                ],
            )
        ],
        marketplace_id="ATVPDKIKX0DER",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
    )

    row = prepared.rows[0]
    assert row.management_include is False
    assert row.management_role == "zero_value_unit_cogs_reference"
    assert row.review_required is False
    assert len(row.unit_events) == 1
    assert row.unit_events[0]["seller_sku"] == "SKU-ZERO"
    assert row.unit_events[0]["quantity"] == 1

    summary = prepared.compact_summary()
    assert summary["management_operating_before_ads_replacement"] == "0.00"
    assert summary["product_sales_amount"] == "0.00"
    assert summary["shipment_unit_count"] == 1
    assert summary["management_unit_count"] == 1


def test_nonzero_released_shipment_remains_prior_period_reference_without_units() -> None:
    prepared = prepare_natural_month_transactions(
        [
            _tx(
                "released-prior-period",
                status="RELEASED",
                typ="Shipment",
                posted="2026-06-10T12:00:00Z",
                amount="25.00",
                breakdowns=_shipment_breakdowns("30.00"),
                items=[
                    {
                        "contexts": [
                            {
                                "contextType": "ProductContext",
                                "sku": "SKU-OLD",
                                "quantityShipped": 1,
                            }
                        ]
                    }
                ],
            )
        ],
        marketplace_id="ATVPDKIKX0DER",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
    )

    row = prepared.rows[0]
    assert row.management_role == "prior_period_release_reference"
    assert row.management_include is False
    assert row.unit_events == ()
    assert prepared.compact_summary()["management_unit_count"] == 0


def test_zero_value_released_shipment_with_missing_unit_context_requires_review() -> None:
    prepared = prepare_natural_month_transactions(
        [
            _tx(
                "zero-value-missing-unit",
                status="RELEASED",
                typ="Shipment",
                posted="2026-06-10T12:00:00Z",
                amount="0.00",
                breakdowns=_shipment_breakdowns("0.00"),
                items=[{"contexts": [{"contextType": "ProductContext", "asin": "B000ZERO"}]}],
            )
        ],
        marketplace_id="ATVPDKIKX0DER",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
    )

    row = prepared.rows[0]
    assert row.management_role == "zero_value_unit_cogs_reference"
    assert row.review_required is True
    assert row.unit_events == ()
    assert prepared.review_required_count == 1
    assert any("unit-event coverage incomplete" in warning for warning in prepared.warnings)
