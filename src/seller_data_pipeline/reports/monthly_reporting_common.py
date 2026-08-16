from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from seller_data_pipeline.services.monthly_financial_close_service import (
        MonthlyFinancialCloseResult,
    )

ZERO = Decimal("0")

MONEY_FORMAT = '$#,##0.00;-$#,##0.00;-'
PERCENT_FORMAT = '0.00%;-0.00%;-'
INTEGER_FORMAT = '#,##0;-#,##0;-'

DARK_BLUE = "17365D"
MID_BLUE = "1F4E78"
LIGHT_BLUE = "D9EAF7"
HEADER_BLUE = "D9E1F2"
GREEN_FILL = "E2F0D9"
YELLOW_FILL = "FFF2CC"
GRAY_FILL = "E7E6E6"
WHITE = "FFFFFF"
BLACK = "000000"


def as_decimal(value: Any) -> Decimal:
    if value in (None, ""):
        return ZERO
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return ZERO


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def safe_ratio(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator == ZERO:
        return None
    return numerator / denominator


def operational_metric(
    result: MonthlyFinancialCloseResult,
    group: str,
    name: str,
) -> Decimal | int | str | None:
    for metric in result.operational_context:
        if metric.metric_group == group and metric.metric_name == name:
            return metric.value
    return None


def summarize_finance_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Decimal]:
    """Aggregate normalized Finances rows into report-friendly components.

    Management-included rows are the de-duplicated natural-month operating rows.
    ProductAdsPayment rows use the explicit replace-with-Ads flag and Transfer is
    kept as a cash reference only. Raw breakdowns are used only to identify the
    true Commission/Base + Commission/Promo net so we do not overstate commission.
    """

    totals: defaultdict[str, Decimal] = defaultdict(lambda: ZERO)
    for row in rows:
        amount = as_decimal(row.get("amount"))
        transaction_type = str(row.get("transaction_type") or "")
        management_include = as_bool(row.get("management_include"))
        replace_ads = as_bool(row.get("management_replace_with_ads_api"))
        role = str(row.get("management_role") or "")

        if as_bool(row.get("review_required")):
            totals["review_required_count"] += Decimal("1")
            totals["review_required_amount"] += amount
        if management_include:
            totals["operating_net_before_ads"] += amount
        if replace_ads:
            totals["posted_ads_reference"] += amount
        if role == "cash_transfer_reference":
            totals["transfer_reference"] += amount

        if not management_include:
            continue

        if transaction_type == "Shipment":
            totals["shipment_total"] += amount
            totals["product_sales"] += as_decimal(row.get("product_sales_amount"))
            totals["shipping_income"] += as_decimal(row.get("shipping_amount"))
            totals["order_promotion"] += as_decimal(row.get("promotion_amount"))
            totals["fba_fulfillment"] += as_decimal(row.get("fba_fulfillment_fee"))
            totals["shipping_chargeback"] += as_decimal(row.get("shipping_chargeback"))
            leaf = raw_leaf_totals(row.get("raw_transaction_json"))
            totals["commission_base"] += leaf.get(
                "Expenses/AmazonFees/Commission/Base", ZERO
            )
            totals["commission_promo"] += leaf.get(
                "Expenses/AmazonFees/Commission/Promo", ZERO
            )
        elif transaction_type == "Refund":
            totals["refund_total"] += amount
            totals["refund_product"] += as_decimal(row.get("refund_product_amount"))
            totals["refund_shipping"] += as_decimal(row.get("refund_shipping_amount"))
            totals["refund_promotion"] += as_decimal(row.get("refund_promotion_amount"))
        elif transaction_type == "RemovalShipment":
            totals["liquidation_total"] += amount
            totals["liquidation_revenue"] += as_decimal(row.get("liquidation_revenue"))
            totals["liquidation_fee"] += as_decimal(row.get("liquidation_fee"))
        elif transaction_type == "ServiceFee":
            totals["service_fee_total"] += amount
            totals["subscription"] += as_decimal(row.get("subscription_fee"))
            totals["coupon"] += as_decimal(row.get("coupon_fee"))
            totals["deal"] += as_decimal(row.get("deal_fee"))
            totals["storage"] += as_decimal(row.get("storage_fee"))
            totals["customer_return"] += as_decimal(row.get("customer_return_fee"))
            totals["other_service"] += as_decimal(row.get("other_service_fee"))
        elif transaction_type == "FBAInventoryReimbursement":
            totals["reimbursement"] += amount
        elif transaction_type == "MiscellaneousLedgerAdjustment":
            totals["adjustment"] += amount

    totals["net_commission"] = totals["commission_base"] + totals["commission_promo"]
    totals["account_fees"] = (
        totals["subscription"]
        + totals["coupon"]
        + totals["deal"]
        + totals["storage"]
        + totals["customer_return"]
        + totals["other_service"]
    )
    totals["accounting_transaction_net"] = (
        totals["operating_net_before_ads"] + totals["posted_ads_reference"]
    )
    return dict(totals)


def raw_leaf_totals(raw_transaction_json: Any) -> dict[str, Decimal]:
    if not raw_transaction_json:
        return {}
    if isinstance(raw_transaction_json, str):
        try:
            payload = json.loads(raw_transaction_json)
        except json.JSONDecodeError:
            return {}
    elif isinstance(raw_transaction_json, Mapping):
        payload = raw_transaction_json
    else:
        return {}

    breakdowns = payload.get("breakdowns") if isinstance(payload, Mapping) else None
    totals: defaultdict[str, Decimal] = defaultdict(lambda: ZERO)

    def walk(nodes: Any, prefix: tuple[str, ...] = ()) -> None:
        if not isinstance(nodes, list):
            return
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            kind = str(node.get("breakdownType") or "<missing>")
            path = prefix + (kind,)
            children = node.get("breakdowns") or []
            if children:
                walk(children, path)
                continue
            amount = node.get("breakdownAmount") or {}
            if isinstance(amount, Mapping):
                totals["/".join(path)] += as_decimal(amount.get("currencyAmount"))

    walk(breakdowns)
    return dict(totals)


def month_finance_value(
    finance_rows_by_month: Mapping[str, Sequence[Mapping[str, Any]]] | None,
    month: str,
) -> dict[str, Decimal]:
    if not finance_rows_by_month:
        return {}
    return summarize_finance_rows(finance_rows_by_month.get(month, ()))


def sorted_recent_results(
    current: MonthlyFinancialCloseResult,
    recent_results: Sequence[MonthlyFinancialCloseResult] | None,
) -> list[MonthlyFinancialCloseResult]:
    by_month = {current.month: current}
    for item in recent_results or ():
        by_month[item.month] = item
    return [by_month[key] for key in sorted(by_month)[-3:]]


__all__ = [
    "BLACK",
    "DARK_BLUE",
    "GRAY_FILL",
    "GREEN_FILL",
    "HEADER_BLUE",
    "INTEGER_FORMAT",
    "LIGHT_BLUE",
    "MID_BLUE",
    "MONEY_FORMAT",
    "PERCENT_FORMAT",
    "WHITE",
    "YELLOW_FILL",
    "as_bool",
    "as_decimal",
    "month_finance_value",
    "operational_metric",
    "raw_leaf_totals",
    "safe_ratio",
    "sorted_recent_results",
    "summarize_finance_rows",
]
