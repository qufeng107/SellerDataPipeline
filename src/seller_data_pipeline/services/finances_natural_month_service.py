from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

from seller_data_pipeline.integrations.amazon.marketplaces import (
    expected_marketplace_currency,
    expected_marketplace_timezone,
)

ZERO = Decimal("0")

# Empirically reconciled against Seller Central Monthly Transaction exports for
# 2026-05, 2026-06 and 2026-07 on the US marketplace. Keep the policy explicit
# and fail closed for new non-zero transaction/status combinations.
_NATURAL_MONTH_POLICY: dict[tuple[str, str], tuple[str, bool, bool]] = {
    ("Shipment", "DEFERRED"): ("operating_provisional", True, False),
    ("Shipment", "DEFERRED_RELEASED"): ("operating", True, False),
    ("Shipment", "RELEASED"): ("prior_period_release_reference", False, False),
    ("Refund", "RELEASED"): ("operating", True, False),
    ("Refund", "DEFERRED_RELEASED"): ("prior_period_release_reference", False, False),
    ("RemovalShipment", "DEFERRED"): ("operating", True, False),
    ("RemovalShipment", "DEFERRED_RELEASED"): ("operating", True, False),
    ("RemovalShipment", "RELEASED"): ("prior_period_release_reference", False, False),
    ("ProductAdsPayment", "RELEASED"): ("ads_charge_reference", False, True),
    ("ServiceFee", "RELEASED"): ("operating", True, False),
    ("FBAInventoryReimbursement", "RELEASED"): ("operating", True, False),
    ("MiscellaneousLedgerAdjustment", "RELEASED"): ("operating", True, False),
    ("Transfer", "RELEASED"): ("cash_transfer_reference", False, False),
    ("Retrocharge", "RELEASED"): ("non_operating_reference", False, False),
}


@dataclass(frozen=True)
class FinanceNaturalMonthRow:
    marketplace_id: str
    transaction_id: str
    transaction_status: str
    transaction_type: str
    description: str | None
    posted_at_utc: datetime
    posted_at_local: datetime
    posted_date_local: date
    marketplace_timezone: str
    amount: Decimal
    currency: str | None
    settlement_id: str | None
    order_id: str | None
    deferred_transaction_id: str | None
    release_transaction_id: str | None
    management_role: str
    management_include: bool
    management_replace_with_ads_api: bool
    review_required: bool
    product_sales_amount: Decimal
    shipping_amount: Decimal
    promotion_amount: Decimal
    fba_fulfillment_fee: Decimal
    shipping_chargeback: Decimal
    refund_product_amount: Decimal
    refund_shipping_amount: Decimal
    refund_promotion_amount: Decimal
    liquidation_revenue: Decimal
    liquidation_fee: Decimal
    subscription_fee: Decimal
    coupon_fee: Decimal
    deal_fee: Decimal
    storage_fee: Decimal
    customer_return_fee: Decimal
    other_service_fee: Decimal
    unit_events: tuple[dict[str, Any], ...]
    related_identifiers_json: str
    raw_transaction_json: str
    raw_transaction_hash: str
    business_key_hash: str

    def to_db_row(self) -> dict[str, Any]:
        return {
            "marketplace_id": self.marketplace_id,
            "transaction_id": self.transaction_id,
            "transaction_status": self.transaction_status,
            "transaction_type": self.transaction_type,
            "description": self.description,
            "posted_at_utc": self.posted_at_utc.astimezone(UTC).replace(tzinfo=None),
            "posted_at_local": self.posted_at_local.replace(tzinfo=None),
            "posted_date_local": self.posted_date_local,
            "marketplace_timezone": self.marketplace_timezone,
            "amount": self.amount,
            "currency": self.currency,
            "settlement_id": self.settlement_id,
            "order_id": self.order_id,
            "deferred_transaction_id": self.deferred_transaction_id,
            "release_transaction_id": self.release_transaction_id,
            "management_role": self.management_role,
            "management_include": self.management_include,
            "management_replace_with_ads_api": self.management_replace_with_ads_api,
            "review_required": self.review_required,
            "product_sales_amount": self.product_sales_amount,
            "shipping_amount": self.shipping_amount,
            "promotion_amount": self.promotion_amount,
            "fba_fulfillment_fee": self.fba_fulfillment_fee,
            "shipping_chargeback": self.shipping_chargeback,
            "refund_product_amount": self.refund_product_amount,
            "refund_shipping_amount": self.refund_shipping_amount,
            "refund_promotion_amount": self.refund_promotion_amount,
            "liquidation_revenue": self.liquidation_revenue,
            "liquidation_fee": self.liquidation_fee,
            "subscription_fee": self.subscription_fee,
            "coupon_fee": self.coupon_fee,
            "deal_fee": self.deal_fee,
            "storage_fee": self.storage_fee,
            "customer_return_fee": self.customer_return_fee,
            "other_service_fee": self.other_service_fee,
            "unit_events_json": _json_dumps(list(self.unit_events)),
            "related_identifiers_json": self.related_identifiers_json,
            "raw_transaction_json": self.raw_transaction_json,
            "raw_transaction_hash": self.raw_transaction_hash,
            "business_key_hash": self.business_key_hash,
        }


@dataclass(frozen=True)
class FinanceNaturalMonthPrepared:
    marketplace_id: str
    month: str
    start_date: date
    end_date: date
    timezone_name: str
    currency: str | None
    pages_fetched: int
    fetched_transaction_count: int
    local_transaction_count: int
    rows: tuple[FinanceNaturalMonthRow, ...]
    warnings: tuple[str, ...]

    @property
    def review_required_count(self) -> int:
        return sum(1 for row in self.rows if row.review_required)

    @property
    def review_required_amount(self) -> Decimal:
        return sum((row.amount for row in self.rows if row.review_required), ZERO)

    def compact_summary(self) -> dict[str, Any]:
        by_status_type: defaultdict[tuple[str, str], dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "amount": ZERO}
        )
        management_operating = ZERO
        ads_charge_reference = ZERO
        transfer_reference = ZERO
        product_sales = ZERO
        unit_count = 0
        shipment_unit_count = 0
        liquidation_unit_count = 0
        for row in self.rows:
            item = by_status_type[(row.transaction_status, row.transaction_type)]
            item["count"] += 1
            item["amount"] += row.amount
            if row.management_include:
                management_operating += row.amount
            if row.management_replace_with_ads_api:
                ads_charge_reference += row.amount
            if row.management_role == "cash_transfer_reference":
                transfer_reference += row.amount
            if row.management_include and row.transaction_type == "Shipment":
                product_sales += row.product_sales_amount
            if row.management_include and row.transaction_type in {"Shipment", "RemovalShipment"}:
                row_units = sum(int(event.get("quantity") or 0) for event in row.unit_events)
                unit_count += row_units
                if row.transaction_type == "Shipment":
                    shipment_unit_count += row_units
                else:
                    liquidation_unit_count += row_units
        return {
            "schema_version": "v1.90-natural-month-finances",
            "marketplace_id": self.marketplace_id,
            "month": self.month,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "timezone": self.timezone_name,
            "currency": self.currency,
            "pages_fetched": self.pages_fetched,
            "fetched_transaction_count": self.fetched_transaction_count,
            "local_transaction_count": self.local_transaction_count,
            "prepared_row_count": len(self.rows),
            "review_required_count": self.review_required_count,
            "review_required_amount": _decimal_string(self.review_required_amount),
            "management_operating_before_ads_replacement": _decimal_string(management_operating),
            "finances_ads_charge_reference": _decimal_string(ads_charge_reference),
            "transfer_reference": _decimal_string(transfer_reference),
            "product_sales_amount": _decimal_string(product_sales),
            "management_unit_count": unit_count,
            "shipment_unit_count": shipment_unit_count,
            "liquidation_unit_count": liquidation_unit_count,
            "status_type_totals": {
                f"{status}|{typ}": {
                    "count": value["count"],
                    "amount": _decimal_string(value["amount"]),
                }
                for (status, typ), value in sorted(by_status_type.items())
            },
            "warnings": list(self.warnings),
        }


def natural_month_utc_fetch_window(
    *, marketplace_id: str, start_date: date, end_date: date
) -> tuple[datetime, datetime, str]:
    timezone_name = expected_marketplace_timezone(marketplace_id)
    if not timezone_name:
        raise ValueError(
            f"No verified marketplace timezone configured for marketplace_id={marketplace_id}"
        )
    tz = ZoneInfo(timezone_name)
    local_start = datetime.combine(start_date, time.min, tzinfo=tz)
    local_end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=tz)
    # Deliberate padding: Finances API filtering is UTC while management month is local.
    return (
        local_start.astimezone(UTC) - timedelta(days=1),
        local_end.astimezone(UTC) + timedelta(days=1),
        timezone_name,
    )


def prepare_natural_month_transactions(
    transactions: Iterable[Mapping[str, Any]],
    *,
    marketplace_id: str,
    start_date: date,
    end_date: date,
    pages_fetched: int = 0,
    fetched_transaction_count: int | None = None,
) -> FinanceNaturalMonthPrepared:
    fetch_rows = list(transactions)
    timezone_name = expected_marketplace_timezone(marketplace_id)
    if not timezone_name:
        raise ValueError(
            f"No verified marketplace timezone configured for marketplace_id={marketplace_id}"
        )
    expected_currency = expected_marketplace_currency(marketplace_id)
    tz = ZoneInfo(timezone_name)
    rows: list[FinanceNaturalMonthRow] = []
    warnings: list[str] = []
    seen_transaction_ids: set[str] = set()

    for transaction in fetch_rows:
        transaction_id = _text(transaction.get("transactionId"))
        if not transaction_id:
            warnings.append("Finances API row missing transactionId; row skipped")
            continue
        if transaction_id in seen_transaction_ids:
            raise ValueError(f"Duplicate Finances transactionId in one fetch: {transaction_id}")
        seen_transaction_ids.add(transaction_id)

        posted_at_utc = _parse_datetime(transaction.get("postedDate"))
        if posted_at_utc is None:
            warnings.append(f"transaction_id={transaction_id} missing/invalid postedDate; row skipped")
            continue
        posted_at_local = posted_at_utc.astimezone(tz)
        if not (start_date <= posted_at_local.date() <= end_date):
            continue

        transaction_status = _text(transaction.get("transactionStatus")) or "<missing>"
        transaction_type = _text(transaction.get("transactionType")) or "<missing>"
        currency, amount = _currency_amount(transaction.get("totalAmount"))
        policy = _NATURAL_MONTH_POLICY.get((transaction_type, transaction_status))
        if policy is None:
            role = "review"
            management_include = False
            replace_ads = False
            review_required = amount != ZERO
        else:
            role, management_include, replace_ads = policy
            review_required = False
            if role == "non_operating_reference" and amount != ZERO:
                review_required = True

        if expected_currency and currency and currency.upper() != expected_currency.upper():
            review_required = True
            role = "review"
            management_include = False
            replace_ads = False
            warnings.append(
                f"transaction_id={transaction_id} currency={currency} expected={expected_currency}"
            )

        identifiers = _identifier_map(transaction.get("relatedIdentifiers"))
        leaf_totals = _transaction_leaf_totals(transaction.get("breakdowns"))
        raw_json = _json_dumps(transaction)
        raw_hash = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
        business_hash = _business_key_hash(marketplace_id, transaction_id)
        unit_events = tuple(
            _extract_unit_events(
                transaction,
                posted_date=posted_at_local.date(),
                transaction_type=transaction_type,
                management_include=management_include,
            )
        )
        if management_include and transaction_type in {"Shipment", "RemovalShipment"}:
            item_count = len(_list_of_mappings(transaction.get("items")))
            if item_count == 0 or len(unit_events) != item_count:
                review_required = True
                warnings.append(
                    "transaction_id="
                    f"{transaction_id} unit-event coverage incomplete: "
                    f"items={item_count} extracted={len(unit_events)}"
                )
        subscription_fee = _leaf_contains_sum(leaf_totals, "Subscription")
        coupon_fee = _leaf_contains_sum(leaf_totals, "Coupon")
        deal_fee = _leaf_contains_sum(leaf_totals, "Deal")
        storage_fee = _leaf_contains_sum(leaf_totals, "Storage")
        customer_return_fee = _leaf_any_contains_sum(
            leaf_totals, ("CustomerReturn", "HRR")
        )
        identified_service_fee = (
            subscription_fee + coupon_fee + deal_fee + storage_fee + customer_return_fee
        )
        other_service_fee = (
            amount - identified_service_fee if transaction_type == "ServiceFee" else ZERO
        )
        rows.append(
            FinanceNaturalMonthRow(
                marketplace_id=marketplace_id,
                transaction_id=transaction_id,
                transaction_status=transaction_status,
                transaction_type=transaction_type,
                description=_text(transaction.get("description")),
                posted_at_utc=posted_at_utc,
                posted_at_local=posted_at_local,
                posted_date_local=posted_at_local.date(),
                marketplace_timezone=timezone_name,
                amount=amount,
                currency=currency,
                settlement_id=identifiers.get("SETTLEMENT_ID"),
                order_id=identifiers.get("ORDER_ID"),
                deferred_transaction_id=identifiers.get("DEFERRED_TRANSACTION_ID"),
                release_transaction_id=identifiers.get("RELEASE_TRANSACTION_ID"),
                management_role=role,
                management_include=management_include,
                management_replace_with_ads_api=replace_ads,
                review_required=review_required,
                product_sales_amount=_leaf_sum(leaf_totals, "Sales/ProductCharges"),
                shipping_amount=_leaf_sum(leaf_totals, "Sales/Shipping"),
                promotion_amount=_leaf_sum(leaf_totals, "Expenses/PromoRebates"),
                fba_fulfillment_fee=_leaf_contains_sum(
                    leaf_totals, "FBAPerUnitFulfillmentFee"
                ),
                shipping_chargeback=_leaf_contains_sum(leaf_totals, "ShippingChargeback"),
                refund_product_amount=_leaf_sum(leaf_totals, "Refunded Sales/ProductCharges"),
                refund_shipping_amount=_leaf_sum(leaf_totals, "Refunded Sales/Shipping"),
                refund_promotion_amount=_leaf_sum(
                    leaf_totals, "Refunded Expenses/PromoRebates"
                ),
                liquidation_revenue=_leaf_sum(leaf_totals, "Sales/RecommerceLiquidation"),
                liquidation_fee=(
                    _leaf_contains_sum(leaf_totals, "LiquidationProcessingFee")
                    + _leaf_contains_sum(leaf_totals, "LiquidationReferralFee")
                ),
                subscription_fee=subscription_fee,
                coupon_fee=coupon_fee,
                deal_fee=deal_fee,
                storage_fee=storage_fee,
                customer_return_fee=customer_return_fee,
                other_service_fee=other_service_fee,
                unit_events=unit_events,
                related_identifiers_json=_json_dumps(
                    transaction.get("relatedIdentifiers") or []
                ),
                raw_transaction_json=raw_json,
                raw_transaction_hash=raw_hash,
                business_key_hash=business_hash,
            )
        )

    month = f"{start_date.year:04d}-{start_date.month:02d}"
    return FinanceNaturalMonthPrepared(
        marketplace_id=marketplace_id,
        month=month,
        start_date=start_date,
        end_date=end_date,
        timezone_name=timezone_name,
        currency=expected_currency,
        pages_fetched=pages_fetched,
        fetched_transaction_count=(
            len(fetch_rows) if fetched_transaction_count is None else fetched_transaction_count
        ),
        local_transaction_count=len(rows),
        rows=tuple(rows),
        warnings=tuple(warnings),
    )


def _transaction_leaf_totals(value: Any) -> dict[str, Decimal]:
    totals: defaultdict[str, Decimal] = defaultdict(lambda: ZERO)

    def walk(nodes: Any, prefix: tuple[str, ...] = ()) -> None:
        if not isinstance(nodes, list):
            return
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            kind = _text(node.get("breakdownType")) or "<missing>"
            path = prefix + (kind,)
            children = node.get("breakdowns") or []
            if children:
                walk(children, path)
                continue
            _, amount = _currency_amount(node.get("breakdownAmount"))
            totals["/".join(path)] += amount

    walk(value)
    return dict(totals)


def _extract_unit_events(
    transaction: Mapping[str, Any],
    *,
    posted_date: date,
    transaction_type: str,
    management_include: bool,
) -> list[dict[str, Any]]:
    if not management_include or transaction_type not in {"Shipment", "RemovalShipment"}:
        return []
    events: list[dict[str, Any]] = []
    for item_index, item in enumerate(_list_of_mappings(transaction.get("items")), start=1):
        sku: str | None = _text(item.get("sku")) or _text(item.get("sellerSku"))
        quantity: int | None = _positive_int(item.get("quantityShipped")) or _positive_int(
            item.get("quantity")
        )
        asin = _text(item.get("asin"))
        for context in _list_of_mappings(item.get("contexts")):
            sku = sku or _text(context.get("sku")) or _text(context.get("sellerSku"))
            asin = asin or _text(context.get("asin"))
            quantity = (
                quantity
                or _positive_int(context.get("quantityShipped"))
                or _positive_int(context.get("quantity"))
                or _positive_int(context.get("quantityPurchased"))
            )
        if not sku or not quantity:
            continue
        events.append(
            {
                "seller_sku": sku,
                "asin": asin,
                "quantity": quantity,
                "posted_date": posted_date.isoformat(),
                "item_index": item_index,
                "transaction_type": transaction_type,
            }
        )
    return events


def _identifier_map(value: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    for identifier in _list_of_mappings(value):
        name = _text(identifier.get("relatedIdentifierName"))
        identifier_value = _text(identifier.get("relatedIdentifierValue"))
        if name and identifier_value and name not in result:
            result[name] = identifier_value
    return result


def _leaf_sum(totals: Mapping[str, Decimal], exact_path: str) -> Decimal:
    return sum((amount for path, amount in totals.items() if path == exact_path), ZERO)


def _leaf_contains_sum(totals: Mapping[str, Decimal], needle: str) -> Decimal:
    return sum((amount for path, amount in totals.items() if needle in path), ZERO)


def _leaf_any_contains_sum(
    totals: Mapping[str, Decimal], needles: tuple[str, ...]
) -> Decimal:
    return sum(
        (amount for path, amount in totals.items() if any(needle in path for needle in needles)),
        ZERO,
    )


def _currency_amount(value: Any) -> tuple[str | None, Decimal]:
    if not isinstance(value, Mapping):
        return None, ZERO
    currency = _text(value.get("currencyCode"))
    return currency, _decimal(value.get("currencyAmount"))


def _decimal(value: Any) -> Decimal:
    if value in (None, ""):
        return ZERO
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return ZERO


def _positive_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _parse_datetime(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        result = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=UTC)
    return result.astimezone(UTC)


def _list_of_mappings(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _json_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_ready(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(child) for child in value]
    return value


def _json_dumps(value: Any) -> str:
    return json.dumps(
        _json_ready(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _business_key_hash(marketplace_id: str, transaction_id: str) -> str:
    canonical = _json_dumps(
        {
            "target_table": "amazon_finance_transaction",
            "marketplace_id": marketplace_id,
            "transaction_id": transaction_id,
        }
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _decimal_string(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


__all__ = [
    "FinanceNaturalMonthPrepared",
    "FinanceNaturalMonthRow",
    "natural_month_utc_fetch_window",
    "prepare_natural_month_transactions",
]
