from __future__ import annotations

import csv
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Protocol

MONEY_QUANT = Decimal("0.01")
ZERO = Decimal("0")
PRODUCT_SALES_CATEGORIES = {"product_sales", "liquidation_revenue"}


@dataclass(frozen=True)
class ProfitInput:
    sales_amount: Decimal
    amazon_fees: Decimal = Decimal("0")
    fba_fees: Decimal = Decimal("0")
    refund_amount: Decimal = Decimal("0")
    ad_spend: Decimal = Decimal("0")
    promotion_cost: Decimal = Decimal("0")
    product_cost: Decimal = Decimal("0")
    first_mile_cost: Decimal = Decimal("0")
    other_cost: Decimal = Decimal("0")


@dataclass(frozen=True)
class SettlementProfitLine:
    id: int | None
    marketplace_id: str
    posted_date: date | None
    amount: Decimal
    currency: str | None
    settlement_id: str | None = None
    transaction_type: str | None = None
    order_id: str | None = None
    order_item_code: str | None = None
    seller_sku: str | None = None
    quantity_purchased: int | None = None
    amount_type: str | None = None
    amount_description: str | None = None
    amount_category: str = "unknown"
    profit_bucket: str = "unknown"
    is_settlement_summary: bool = False

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> SettlementProfitLine:
        return cls(
            id=_optional_int(row.get("id")),
            marketplace_id=str(row.get("marketplace_id") or ""),
            posted_date=_parse_date_value(row.get("posted_date")),
            amount=_to_decimal(row.get("amount")),
            currency=_empty_to_none(row.get("currency")),
            settlement_id=_empty_to_none(row.get("settlement_id")),
            transaction_type=_empty_to_none(row.get("transaction_type")),
            order_id=_empty_to_none(row.get("order_id")),
            order_item_code=_empty_to_none(row.get("order_item_code")),
            seller_sku=_empty_to_none(row.get("seller_sku")),
            quantity_purchased=_optional_int(row.get("quantity_purchased")),
            amount_type=_empty_to_none(row.get("amount_type")),
            amount_description=_empty_to_none(row.get("amount_description")),
            amount_category=str(row.get("amount_category") or "unknown"),
            profit_bucket=str(row.get("profit_bucket") or "unknown"),
            is_settlement_summary=bool(row.get("is_settlement_summary") or False),
        )


@dataclass(frozen=True)
class SkuCostRecord:
    marketplace_id: str
    seller_sku: str
    asin: str | None
    product_cost: Decimal
    first_mile_cost: Decimal
    packaging_cost: Decimal
    other_unit_cost: Decimal
    currency: str
    effective_from: date
    effective_to: date | None = None
    remark: str | None = None

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> SkuCostRecord:
        return cls(
            marketplace_id=str(row.get("marketplace_id") or ""),
            seller_sku=str(row.get("seller_sku") or ""),
            asin=_empty_to_none(row.get("asin")),
            product_cost=_to_decimal(row.get("product_cost")),
            first_mile_cost=_to_decimal(row.get("first_mile_cost")),
            packaging_cost=_to_decimal(row.get("packaging_cost")),
            other_unit_cost=_to_decimal(row.get("other_unit_cost")),
            currency=str(row.get("currency") or ""),
            effective_from=_required_date(row.get("effective_from"), "effective_from"),
            effective_to=_parse_date_value(row.get("effective_to")),
            remark=_empty_to_none(row.get("remark")),
        )

    @property
    def unit_standard_cost(self) -> Decimal:
        return self.product_cost + self.first_mile_cost + self.packaging_cost + self.other_unit_cost

    def is_effective_on(self, value: date) -> bool:
        if value < self.effective_from:
            return False
        return self.effective_to is None or value <= self.effective_to


@dataclass(frozen=True)
class SkuProfitRow:
    seller_sku: str
    units: int
    product_sales_amount: Decimal
    settlement_net_amount: Decimal
    unit_standard_cost: Decimal | None
    internal_cogs: Decimal
    estimated_profit_after_cogs: Decimal
    currency: str | None
    cost_currency: str | None
    status: str
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "seller_sku": self.seller_sku,
            "units": self.units,
            "product_sales_amount": _decimal_to_string(self.product_sales_amount),
            "settlement_net_amount": _decimal_to_string(self.settlement_net_amount),
            "unit_standard_cost": _optional_decimal_to_string(self.unit_standard_cost),
            "internal_cogs": _decimal_to_string(self.internal_cogs),
            "estimated_profit_after_cogs": _decimal_to_string(self.estimated_profit_after_cogs),
            "currency": self.currency,
            "cost_currency": self.cost_currency,
            "status": self.status,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class OperationalSummary:
    order_count: int = 0
    order_item_rows: int = 0
    ordered_units: int = 0
    ordered_item_sales_amount: Decimal = ZERO
    order_currency: str | None = None
    ads_cost: Decimal = ZERO
    ads_sales_7d: Decimal = ZERO
    ads_clicks: int = 0
    ads_impressions: int = 0
    sales_traffic_units_ordered: int = 0
    sales_traffic_ordered_sales_amount: Decimal = ZERO
    sales_traffic_sessions: int = 0
    sales_traffic_order_items: int = 0

    @classmethod
    def from_mappings(
        cls,
        *,
        orders_summary: Mapping[str, Any] | None = None,
        ads_summary: Mapping[str, Any] | None = None,
        sales_traffic_summary: Mapping[str, Any] | None = None,
    ) -> OperationalSummary:
        orders = orders_summary or {}
        ads = ads_summary or {}
        sales_traffic = sales_traffic_summary or {}
        return cls(
            order_count=_optional_int(orders.get("order_count")) or 0,
            order_item_rows=_optional_int(orders.get("order_item_rows")) or 0,
            ordered_units=_optional_int(orders.get("ordered_units")) or 0,
            ordered_item_sales_amount=_to_decimal(orders.get("ordered_item_sales_amount")),
            order_currency=_empty_to_none(orders.get("currency")),
            ads_cost=_to_decimal(ads.get("ads_cost")),
            ads_sales_7d=_to_decimal(ads.get("ads_sales_7d")),
            ads_clicks=_optional_int(ads.get("ads_clicks")) or 0,
            ads_impressions=_optional_int(ads.get("ads_impressions")) or 0,
            sales_traffic_units_ordered=(
                _optional_int(sales_traffic.get("units_ordered")) or 0
            ),
            sales_traffic_ordered_sales_amount=_to_decimal(
                sales_traffic.get("ordered_product_sales_amount")
            ),
            sales_traffic_sessions=_optional_int(sales_traffic.get("sessions")) or 0,
            sales_traffic_order_items=_optional_int(sales_traffic.get("total_order_items")) or 0,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_count": self.order_count,
            "order_item_rows": self.order_item_rows,
            "ordered_units": self.ordered_units,
            "ordered_item_sales_amount": _decimal_to_string(self.ordered_item_sales_amount),
            "order_currency": self.order_currency,
            "ads_cost": _decimal_to_string(self.ads_cost),
            "ads_sales_7d": _decimal_to_string(self.ads_sales_7d),
            "ads_clicks": self.ads_clicks,
            "ads_impressions": self.ads_impressions,
            "sales_traffic_units_ordered": self.sales_traffic_units_ordered,
            "sales_traffic_ordered_sales_amount": _decimal_to_string(
                self.sales_traffic_ordered_sales_amount
            ),
            "sales_traffic_sessions": self.sales_traffic_sessions,
            "sales_traffic_order_items": self.sales_traffic_order_items,
        }


@dataclass(frozen=True)
class ProfitReportResult:
    marketplace_id: str
    start_date: date
    end_date: date
    status: str
    currency: str | None
    settlement_row_count: int
    settlement_net_amount: Decimal
    internal_cogs: Decimal
    estimated_operating_profit: Decimal
    product_sales_units: int
    product_sales_amount: Decimal
    bucket_totals: dict[str, Decimal]
    category_totals: dict[str, Decimal]
    sku_rows: tuple[SkuProfitRow, ...]
    operational_summary: OperationalSummary
    missing_cost_skus: tuple[str, ...] = ()
    currency_mismatch_skus: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    output_files: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "marketplace_id": self.marketplace_id,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "status": self.status,
            "currency": self.currency,
            "settlement_row_count": self.settlement_row_count,
            "settlement_net_amount": _decimal_to_string(self.settlement_net_amount),
            "internal_cogs": _decimal_to_string(self.internal_cogs),
            "estimated_operating_profit": _decimal_to_string(
                self.estimated_operating_profit
            ),
            "product_sales_units": self.product_sales_units,
            "product_sales_amount": _decimal_to_string(self.product_sales_amount),
            "bucket_totals": _decimal_dict_to_string(self.bucket_totals),
            "category_totals": _decimal_dict_to_string(self.category_totals),
            "sku_rows": [row.to_dict() for row in self.sku_rows],
            "operational_summary": self.operational_summary.to_dict(),
            "missing_cost_skus": list(self.missing_cost_skus),
            "currency_mismatch_skus": list(self.currency_mismatch_skus),
            "warnings": list(self.warnings),
            "output_files": dict(self.output_files),
        }

    def with_output_files(self, output_files: Mapping[str, str]) -> ProfitReportResult:
        return ProfitReportResult(
            marketplace_id=self.marketplace_id,
            start_date=self.start_date,
            end_date=self.end_date,
            status=self.status,
            currency=self.currency,
            settlement_row_count=self.settlement_row_count,
            settlement_net_amount=self.settlement_net_amount,
            internal_cogs=self.internal_cogs,
            estimated_operating_profit=self.estimated_operating_profit,
            product_sales_units=self.product_sales_units,
            product_sales_amount=self.product_sales_amount,
            bucket_totals=self.bucket_totals,
            category_totals=self.category_totals,
            sku_rows=self.sku_rows,
            operational_summary=self.operational_summary,
            missing_cost_skus=self.missing_cost_skus,
            currency_mismatch_skus=self.currency_mismatch_skus,
            warnings=self.warnings,
            output_files=dict(output_files),
        )


class ProfitDataRepo(Protocol):
    def fetch_settlement_profit_rows(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        ...

    def fetch_sku_cost_rows(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        ...

    def fetch_orders_period_summary(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        ...

    def fetch_ads_period_summary(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        ...

    def fetch_sales_traffic_period_summary(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        ...


class CalculateProfitService:
    def __init__(self, repo: ProfitDataRepo | None = None) -> None:
        self.repo = repo

    def estimate_profit(self, data: ProfitInput) -> Decimal:
        return (
            data.sales_amount
            - data.amazon_fees
            - data.fba_fees
            - data.refund_amount
            - data.ad_spend
            - data.promotion_cost
            - data.product_cost
            - data.first_mile_cost
            - data.other_cost
        )

    def run(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
        output_root: str | Path | None = None,
    ) -> ProfitReportResult:
        if self.repo is None:
            raise ValueError("CalculateProfitService.run requires a repo")
        self._validate_period(start_date=start_date, end_date=end_date)
        result = self.calculate_from_rows(
            marketplace_id=marketplace_id,
            start_date=start_date,
            end_date=end_date,
            settlement_rows=self.repo.fetch_settlement_profit_rows(
                marketplace_id=marketplace_id,
                start_date=start_date,
                end_date=end_date,
            ),
            sku_cost_rows=self.repo.fetch_sku_cost_rows(
                marketplace_id=marketplace_id,
                start_date=start_date,
                end_date=end_date,
            ),
            orders_summary=self.repo.fetch_orders_period_summary(
                marketplace_id=marketplace_id,
                start_date=start_date,
                end_date=end_date,
            ),
            ads_summary=self.repo.fetch_ads_period_summary(
                marketplace_id=marketplace_id,
                start_date=start_date,
                end_date=end_date,
            ),
            sales_traffic_summary=self.repo.fetch_sales_traffic_period_summary(
                marketplace_id=marketplace_id,
                start_date=start_date,
                end_date=end_date,
            ),
        )
        if output_root is not None:
            return self.write_preview_files(result=result, output_root=output_root)
        return result

    def calculate_from_rows(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
        settlement_rows: Iterable[Mapping[str, Any]],
        sku_cost_rows: Iterable[Mapping[str, Any]],
        orders_summary: Mapping[str, Any] | None = None,
        ads_summary: Mapping[str, Any] | None = None,
        sales_traffic_summary: Mapping[str, Any] | None = None,
    ) -> ProfitReportResult:
        self._validate_period(start_date=start_date, end_date=end_date)
        settlement_lines = [SettlementProfitLine.from_mapping(row) for row in settlement_rows]
        settlement_lines = [line for line in settlement_lines if not line.is_settlement_summary]
        sku_costs = [SkuCostRecord.from_mapping(row) for row in sku_cost_rows]
        cost_index = _build_cost_index(sku_costs)

        bucket_totals = _sum_by(settlement_lines, key_attr="profit_bucket")
        category_totals = _sum_by(settlement_lines, key_attr="amount_category")
        settlement_net_amount = _money(sum((line.amount for line in settlement_lines), ZERO))
        currency = _first_non_empty(line.currency for line in settlement_lines)

        sku_accumulator = _build_sku_accumulator(settlement_lines)
        sku_rows: list[SkuProfitRow] = []
        missing_cost_skus: set[str] = set()
        currency_mismatch_skus: set[str] = set()
        internal_cogs = ZERO
        product_sales_units = 0
        product_sales_amount = ZERO

        for seller_sku in sorted(sku_accumulator):
            sku_data = sku_accumulator[seller_sku]
            units = int(sku_data["units"])
            sku_product_sales = _money(sku_data["product_sales_amount"])
            sku_settlement_net = _money(sku_data["settlement_net_amount"])
            product_sales_units += units
            product_sales_amount += sku_product_sales
            cost, notes = _resolve_cost_for_sku(
                cost_index=cost_index,
                marketplace_id=marketplace_id,
                seller_sku=seller_sku,
                posted_dates=sku_data["posted_dates"],
            )
            status = "ok"
            cost_currency = None
            unit_standard_cost: Decimal | None = None
            sku_cogs = ZERO
            if cost is None:
                status = "missing_cost"
                missing_cost_skus.add(seller_sku)
            else:
                cost_currency = cost.currency
                unit_standard_cost = _money(cost.unit_standard_cost)
                sku_cogs = _money(unit_standard_cost * Decimal(units))
                internal_cogs += sku_cogs
                if currency and cost.currency and cost.currency != currency:
                    status = "currency_mismatch"
                    currency_mismatch_skus.add(seller_sku)
                    notes = (
                        *notes,
                        f"cost currency {cost.currency} != settlement currency {currency}",
                    )
            sku_rows.append(
                SkuProfitRow(
                    seller_sku=seller_sku,
                    units=units,
                    product_sales_amount=sku_product_sales,
                    settlement_net_amount=sku_settlement_net,
                    unit_standard_cost=unit_standard_cost,
                    internal_cogs=sku_cogs,
                    estimated_profit_after_cogs=_money(sku_settlement_net - sku_cogs),
                    currency=currency,
                    cost_currency=cost_currency,
                    status=status,
                    notes=tuple(notes),
                )
            )

        warnings = _build_warnings(
            settlement_row_count=len(settlement_lines),
            missing_cost_skus=missing_cost_skus,
            currency_mismatch_skus=currency_mismatch_skus,
            product_sales_units=product_sales_units,
        )
        status = _result_status(
            settlement_row_count=len(settlement_lines),
            missing_cost_skus=missing_cost_skus,
            currency_mismatch_skus=currency_mismatch_skus,
        )
        return ProfitReportResult(
            marketplace_id=marketplace_id,
            start_date=start_date,
            end_date=end_date,
            status=status,
            currency=currency,
            settlement_row_count=len(settlement_lines),
            settlement_net_amount=settlement_net_amount,
            internal_cogs=_money(internal_cogs),
            estimated_operating_profit=_money(settlement_net_amount - internal_cogs),
            product_sales_units=product_sales_units,
            product_sales_amount=_money(product_sales_amount),
            bucket_totals=_money_dict(bucket_totals),
            category_totals=_money_dict(category_totals),
            sku_rows=tuple(sku_rows),
            operational_summary=OperationalSummary.from_mappings(
                orders_summary=orders_summary,
                ads_summary=ads_summary,
                sales_traffic_summary=sales_traffic_summary,
            ),
            missing_cost_skus=tuple(sorted(missing_cost_skus)),
            currency_mismatch_skus=tuple(sorted(currency_mismatch_skus)),
            warnings=warnings,
        )

    def write_preview_files(
        self,
        *,
        result: ProfitReportResult,
        output_root: str | Path,
    ) -> ProfitReportResult:
        output_dir = Path(output_root) / result.marketplace_id / (
            f"{result.start_date.isoformat()}_{result.end_date.isoformat()}"
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "profit_preview.json"
        markdown_path = output_dir / "profit_preview.md"
        sku_csv_path = output_dir / "sku_profit_detail.csv"

        output_files = {
            "json": str(json_path),
            "markdown": str(markdown_path),
            "sku_csv": str(sku_csv_path),
        }
        result_with_paths = result.with_output_files(output_files)
        json_path.write_text(
            json.dumps(result_with_paths.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        markdown_path.write_text(_render_markdown(result_with_paths), encoding="utf-8")
        _write_sku_csv(sku_csv_path, result_with_paths.sku_rows)
        return result_with_paths

    @staticmethod
    def _validate_period(*, start_date: date, end_date: date) -> None:
        if end_date < start_date:
            raise ValueError("end_date must be >= start_date")


def _build_sku_accumulator(
    settlement_lines: Sequence[SettlementProfitLine],
) -> dict[str, dict[str, Any]]:
    accumulator: dict[str, dict[str, Any]] = {}
    seen_unit_keys: set[tuple[Any, ...]] = set()
    for line in settlement_lines:
        if not line.seller_sku:
            continue
        data = accumulator.setdefault(
            line.seller_sku,
            {
                "units": 0,
                "product_sales_amount": ZERO,
                "settlement_net_amount": ZERO,
                "posted_dates": [],
            },
        )
        data["settlement_net_amount"] += line.amount
        if line.amount_category in PRODUCT_SALES_CATEGORIES:
            data["product_sales_amount"] += line.amount
            unit_key = _unit_dedupe_key(line)
            if unit_key not in seen_unit_keys:
                seen_unit_keys.add(unit_key)
                data["units"] += max(0, line.quantity_purchased or 0)
                if line.posted_date is not None:
                    data["posted_dates"].append(line.posted_date)
    return accumulator


def _unit_dedupe_key(line: SettlementProfitLine) -> tuple[Any, ...]:
    if line.order_item_code:
        return (line.settlement_id, line.order_id, line.order_item_code, line.seller_sku)
    return (line.settlement_id, line.order_id, line.seller_sku, line.id)


def _build_cost_index(costs: Iterable[SkuCostRecord]) -> dict[tuple[str, str], list[SkuCostRecord]]:
    index: dict[tuple[str, str], list[SkuCostRecord]] = defaultdict(list)
    for cost in costs:
        index[(cost.marketplace_id, cost.seller_sku)].append(cost)
    for rows in index.values():
        rows.sort(key=lambda cost: cost.effective_from, reverse=True)
    return dict(index)


def _resolve_cost_for_sku(
    *,
    cost_index: Mapping[tuple[str, str], Sequence[SkuCostRecord]],
    marketplace_id: str,
    seller_sku: str,
    posted_dates: Sequence[date],
) -> tuple[SkuCostRecord | None, tuple[str, ...]]:
    candidates = cost_index.get((marketplace_id, seller_sku), ())
    if not candidates:
        return None, ("no amazon_sku_cost row",)
    if not posted_dates:
        return candidates[0], ("no product-sales posted date; used latest cost row",)
    matched_costs: list[SkuCostRecord] = []
    for posted_date in posted_dates:
        match = next((cost for cost in candidates if cost.is_effective_on(posted_date)), None)
        if match is None:
            return None, (f"no effective cost for posted date {posted_date.isoformat()}",)
        matched_costs.append(match)
    unique_costs = {id(cost) for cost in matched_costs}
    if len(unique_costs) > 1:
        return matched_costs[0], ("multiple cost rows matched inside period; used latest row",)
    return matched_costs[0], ()


def _sum_by(
    settlement_lines: Iterable[SettlementProfitLine],
    *,
    key_attr: str,
) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for line in settlement_lines:
        key = str(getattr(line, key_attr) or "unknown")
        totals[key] += line.amount
    return dict(totals)


def _build_warnings(
    *,
    settlement_row_count: int,
    missing_cost_skus: set[str],
    currency_mismatch_skus: set[str],
    product_sales_units: int,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if settlement_row_count == 0:
        warnings.append("No settlement rows found for this marketplace/date window.")
    if product_sales_units == 0 and settlement_row_count > 0:
        warnings.append("No product-sales units found; SKU COGS may be zero for this period.")
    if missing_cost_skus:
        warnings.append(
            "Missing amazon_sku_cost rows for SKU(s): " + ", ".join(sorted(missing_cost_skus))
        )
    if currency_mismatch_skus:
        warnings.append(
            "Cost currency mismatch for SKU(s): " + ", ".join(sorted(currency_mismatch_skus))
        )
    warnings.append(
        "Preview policy: Settlement is the financial source of truth; Orders/Ads/Sales data "
        "are shown only as operational context."
    )
    return tuple(warnings)


def _result_status(
    *,
    settlement_row_count: int,
    missing_cost_skus: set[str],
    currency_mismatch_skus: set[str],
) -> str:
    if settlement_row_count == 0:
        return "no_data"
    if missing_cost_skus or currency_mismatch_skus:
        return "needs_review"
    return "ok"


def _render_markdown(result: ProfitReportResult) -> str:
    lines = [
        f"# Profit Preview — {result.marketplace_id}",
        "",
        f"Period: `{result.start_date.isoformat()}` to `{result.end_date.isoformat()}`",
        f"Status: `{result.status}`",
        "Policy: `Settlement-led Financial Profit v1.0`",
        f"Currency: `{result.currency or '-'}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Settlement rows | {result.settlement_row_count} |",
        "| Settlement net amount | "
        f"{_format_money(result.settlement_net_amount, result.currency)} |",
        f"| Product-sales units used for COGS | {result.product_sales_units} |",
        f"| Product-sales amount | {_format_money(result.product_sales_amount, result.currency)} |",
        f"| Internal COGS | {_format_money(result.internal_cogs, result.currency)} |",
        "| Estimated operating profit | "
        f"{_format_money(result.estimated_operating_profit, result.currency)} |",
        "",
        "## Settlement bucket totals",
        "",
        "| Profit bucket | Amount |",
        "|---|---:|",
    ]
    for bucket, amount in sorted(result.bucket_totals.items()):
        lines.append(f"| `{bucket}` | {_format_money(amount, result.currency)} |")
    lines.extend(
        [
            "",
            "## SKU detail",
            "",
            "| SKU | Units | Settlement net | COGS | Profit after COGS | Status |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for row in result.sku_rows:
        lines.append(
            "| `{sku}` | {units} | {net} | {cogs} | {profit} | `{status}` |".format(
                sku=row.seller_sku,
                units=row.units,
                net=_format_money(row.settlement_net_amount, result.currency),
                cogs=_format_money(row.internal_cogs, row.cost_currency or result.currency),
                profit=_format_money(row.estimated_profit_after_cogs, result.currency),
                status=row.status,
            )
        )
    op = result.operational_summary
    ordered_sales = _format_money(op.ordered_item_sales_amount, op.order_currency)
    sales_traffic_sales = _format_money(op.sales_traffic_ordered_sales_amount, result.currency)
    lines.extend(
        [
            "",
            "## Operational context (not financial source of truth)",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| Orders | {op.order_count} |",
            f"| Order item rows | {op.order_item_rows} |",
            f"| Ordered units | {op.ordered_units} |",
            f"| Ordered item sales | {ordered_sales} |",
            f"| Ads cost | {_format_money(op.ads_cost, result.currency)} |",
            f"| Ads sales 7d | {_format_money(op.ads_sales_7d, result.currency)} |",
            f"| Ads clicks | {op.ads_clicks} |",
            f"| Ads impressions | {op.ads_impressions} |",
            f"| Sales & Traffic units ordered | {op.sales_traffic_units_ordered} |",
            f"| Sales & Traffic sales | {sales_traffic_sales} |",
            f"| Sales & Traffic sessions | {op.sales_traffic_sessions} |",
            "",
            "## Warnings / review notes",
            "",
        ]
    )
    for warning in result.warnings:
        lines.append(f"- {warning}")
    lines.append("")
    return "\n".join(lines)


def _write_sku_csv(path: Path, rows: Sequence[SkuProfitRow]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "seller_sku",
                "units",
                "product_sales_amount",
                "settlement_net_amount",
                "unit_standard_cost",
                "internal_cogs",
                "estimated_profit_after_cogs",
                "currency",
                "cost_currency",
                "status",
                "notes",
            ),
        )
        writer.writeheader()
        for row in rows:
            payload = row.to_dict()
            payload["notes"] = "; ".join(row.notes)
            writer.writerow(payload)


def _parse_date_value(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def _required_date(value: Any, field_name: str) -> date:
    parsed = _parse_date_value(value)
    if parsed is None:
        raise ValueError(f"{field_name} is required")
    return parsed


def _to_decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return ZERO
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid decimal value: {value!r}") from exc


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _empty_to_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_non_empty(values: Iterable[str | None]) -> str | None:
    for value in values:
        if value:
            return value
    return None


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _money_dict(values: Mapping[str, Decimal]) -> dict[str, Decimal]:
    return {key: _money(value) for key, value in values.items()}


def _decimal_to_string(value: Decimal) -> str:
    return str(_money(value))


def _optional_decimal_to_string(value: Decimal | None) -> str | None:
    return None if value is None else _decimal_to_string(value)


def _decimal_dict_to_string(values: Mapping[str, Decimal]) -> dict[str, str]:
    return {key: _decimal_to_string(value) for key, value in values.items()}


def _format_money(value: Decimal, currency: str | None) -> str:
    prefix = f"{currency} " if currency else ""
    return f"{prefix}{_decimal_to_string(value)}"


__all__ = [
    "CalculateProfitService",
    "OperationalSummary",
    "ProfitInput",
    "ProfitReportResult",
    "SettlementProfitLine",
    "SkuCostRecord",
    "SkuProfitRow",
]
