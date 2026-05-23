from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Protocol

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from seller_data_pipeline.services.calculate_profit_service import (
    PRODUCT_SALES_CATEGORIES,
    SettlementProfitLine,
    SkuCostRecord,
)

MONEY_QUANT = Decimal("0.01")
RATIO_QUANT = Decimal("0.0001")
ZERO = Decimal("0")
REPORT_TYPE = "monthly_financial_close"
REPORT_VERSION = "v1.0"
DEFAULT_OUTPUT_ROOT = "runtime/analysis_reports/monthly_financial_close"
REVIEW_BUCKETS = {"unknown", "unclassified"}
REVIEW_CATEGORIES = {"unknown", "unclassified"}
SKU_PROFIT_SCOPE_NOTE = (
    "SKU profit is before allocation of account-level expenses such as advertising fees, "
    "subscription fees, coupon fees, storage fees, and other non-SKU settlement rows."
)
SETTLEMENT_LED_POLICY_NOTE = (
    "Settlement is the financial source of truth; operational sources are context only."
)


@dataclass(frozen=True)
class WarningEntry:
    warning_code: str
    severity: str
    message: str
    related_sku: str | None = None
    related_source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "warning_code": self.warning_code,
            "severity": self.severity,
            "message": self.message,
            "related_sku": self.related_sku,
            "related_source": self.related_source,
        }


@dataclass(frozen=True)
class ReconciliationCheck:
    check_name: str
    status: str
    severity: str
    expected: str | None
    actual: str | None
    diff: str | None = None
    diff_pct: str | None = None
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_name": self.check_name,
            "status": self.status,
            "severity": self.severity,
            "expected": self.expected,
            "actual": self.actual,
            "diff": self.diff,
            "diff_pct": self.diff_pct,
            "message": self.message,
        }


@dataclass(frozen=True)
class SettlementBucketBreakdownRow:
    profit_bucket: str
    amount: Decimal
    row_count: int
    share_of_product_sales: Decimal | None = None
    share_of_settlement_net: Decimal | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "profit_bucket": self.profit_bucket,
            "amount": _decimal_to_string(self.amount),
            "absolute_amount": _decimal_to_string(abs(self.amount)),
            "share_of_product_sales": _optional_ratio_to_string(self.share_of_product_sales),
            "share_of_settlement_net": _optional_ratio_to_string(self.share_of_settlement_net),
            "row_count": self.row_count,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class AmountCategoryBreakdownRow:
    amount_category: str
    profit_bucket: str
    amount: Decimal
    row_count: int
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "amount_category": self.amount_category,
            "profit_bucket": self.profit_bucket,
            "amount": _decimal_to_string(self.amount),
            "absolute_amount": _decimal_to_string(abs(self.amount)),
            "row_count": self.row_count,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class MonthlySkuProfitRow:
    seller_sku: str
    units: int
    product_sales_amount: Decimal
    settlement_net_amount: Decimal
    unit_standard_cost: Decimal | None
    internal_cogs: Decimal
    estimated_profit_after_cogs: Decimal
    profit_margin: Decimal | None
    revenue_share: Decimal | None
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
            "profit_margin": _optional_ratio_to_string(self.profit_margin),
            "revenue_share": _optional_ratio_to_string(self.revenue_share),
            "currency": self.currency,
            "cost_currency": self.cost_currency,
            "status": self.status,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class OperationalMetric:
    metric_group: str
    metric_name: str
    value: Decimal | int | str | None
    currency: str | None
    source: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_group": self.metric_group,
            "metric_name": self.metric_name,
            "value": _json_value(self.value),
            "currency": self.currency,
            "source": self.source,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class MonthlyFinancialSummary:
    settlement_net_amount: Decimal
    product_sales_amount: Decimal
    product_sales_units: int
    internal_cogs: Decimal
    estimated_operating_profit: Decimal
    profit_margin: Decimal | None
    advertising_cost: Decimal
    fba_fee: Decimal
    amazon_fee: Decimal
    refund: Decimal
    promotion_cost: Decimal
    promotion_fee: Decimal
    reimbursement: Decimal

    def to_dict(self) -> dict[str, Any]:
        return {
            "settlement_net_amount": _decimal_to_string(self.settlement_net_amount),
            "product_sales_amount": _decimal_to_string(self.product_sales_amount),
            "product_sales_units": self.product_sales_units,
            "internal_cogs": _decimal_to_string(self.internal_cogs),
            "estimated_operating_profit": _decimal_to_string(
                self.estimated_operating_profit
            ),
            "profit_margin": _optional_ratio_to_string(self.profit_margin),
            "advertising_cost": _decimal_to_string(self.advertising_cost),
            "fba_fee": _decimal_to_string(self.fba_fee),
            "amazon_fee": _decimal_to_string(self.amazon_fee),
            "refund": _decimal_to_string(self.refund),
            "promotion_cost": _decimal_to_string(self.promotion_cost),
            "promotion_fee": _decimal_to_string(self.promotion_fee),
            "reimbursement": _decimal_to_string(self.reimbursement),
        }


@dataclass(frozen=True)
class MonthlyFinancialCloseResult:
    marketplace_id: str
    profile_id: str | None
    month: str
    start_date: date
    end_date: date
    generated_at_utc: datetime
    status: str
    currency: str | None
    settlement_row_count: int
    financial_summary: MonthlyFinancialSummary
    settlement_bucket_breakdown: tuple[SettlementBucketBreakdownRow, ...]
    amount_category_breakdown: tuple[AmountCategoryBreakdownRow, ...]
    sku_profitability: tuple[MonthlySkuProfitRow, ...]
    operational_context: tuple[OperationalMetric, ...]
    reconciliation_checks: tuple[ReconciliationCheck, ...]
    warnings: tuple[WarningEntry, ...]
    output_files: dict[str, str] = field(default_factory=dict)
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "report_type": REPORT_TYPE,
            "version": REPORT_VERSION,
            "marketplace_id": self.marketplace_id,
            "profile_id": self.profile_id,
            "period": {
                "month": self.month,
                "start_date": self.start_date.isoformat(),
                "end_date": self.end_date.isoformat(),
            },
            "generated_at_utc": self.generated_at_utc.isoformat(),
            "status": self.status,
            "currency": self.currency,
            "settlement_row_count": self.settlement_row_count,
            "executive_summary": self.executive_summary(),
            "financial_summary": self.financial_summary.to_dict(),
            "settlement_bucket_breakdown": [
                row.to_dict() for row in self.settlement_bucket_breakdown
            ],
            "amount_category_breakdown": [
                row.to_dict() for row in self.amount_category_breakdown
            ],
            "sku_profitability": [row.to_dict() for row in self.sku_profitability],
            "operational_context": [metric.to_dict() for metric in self.operational_context],
            "reconciliation_checks": [check.to_dict() for check in self.reconciliation_checks],
            "warnings": [warning.to_dict() for warning in self.warnings],
            "raw_metadata": _json_safe_mapping(self.raw_metadata),
            "methodology_notes": {
                "settlement_led_policy": SETTLEMENT_LED_POLICY_NOTE,
                "sku_profit_scope": SKU_PROFIT_SCOPE_NOTE,
            },
            "output_files": dict(self.output_files),
        }
        return payload

    def with_output_files(
        self,
        output_files: Mapping[str, str],
    ) -> MonthlyFinancialCloseResult:
        return MonthlyFinancialCloseResult(
            marketplace_id=self.marketplace_id,
            profile_id=self.profile_id,
            month=self.month,
            start_date=self.start_date,
            end_date=self.end_date,
            generated_at_utc=self.generated_at_utc,
            status=self.status,
            currency=self.currency,
            settlement_row_count=self.settlement_row_count,
            financial_summary=self.financial_summary,
            settlement_bucket_breakdown=self.settlement_bucket_breakdown,
            amount_category_breakdown=self.amount_category_breakdown,
            sku_profitability=self.sku_profitability,
            operational_context=self.operational_context,
            reconciliation_checks=self.reconciliation_checks,
            warnings=self.warnings,
            raw_metadata=self.raw_metadata,
            output_files=dict(output_files),
        )

    def executive_summary(self) -> dict[str, Any]:
        profit = self.financial_summary.estimated_operating_profit
        margin = self.financial_summary.profit_margin
        headline = (
            f"{self.month} estimated operating profit was "
            f"{_format_money(profit, self.currency)}."
        )
        key_points = [
            (
                "Settlement net amount was "
                f"{_format_money(self.financial_summary.settlement_net_amount, self.currency)}."
            ),
            (
                "Internal COGS was "
                f"{_format_money(self.financial_summary.internal_cogs, self.currency)}."
            ),
            f"Report status is {self.status}.",
        ]
        if margin is not None:
            key_points.insert(1, f"Operating profit margin was {_format_ratio(margin)}.")
        reconciliation_warning_count = sum(
            1 for check in self.reconciliation_checks if check.status == "warning"
        )
        reconciliation_needs_review_count = sum(
            1 for check in self.reconciliation_checks if check.status == "needs_review"
        )
        non_info_warning_count = sum(
            1 for warning in self.warnings if warning.severity != "info"
        )
        if reconciliation_warning_count or reconciliation_needs_review_count:
            key_points.append(
                "Reconciliation warnings: "
                f"{reconciliation_warning_count}; needs_review checks: "
                f"{reconciliation_needs_review_count}."
            )
        if non_info_warning_count:
            key_points.append(f"Non-info warning count: {non_info_warning_count}.")
        return {"headline": headline, "key_points": key_points}


class MonthlyFinancialCloseDataRepo(Protocol):
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
        profile_id: str | None,
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

    def fetch_coupon_period_summary(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        ...

    def fetch_promotion_period_summary(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        ...

    def fetch_fba_reimbursement_period_summary(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        ...


class MonthlyFinancialCloseService:
    def __init__(self, repo: MonthlyFinancialCloseDataRepo | None = None) -> None:
        self.repo = repo

    def run(
        self,
        *,
        marketplace_id: str,
        profile_id: str | None,
        month: str,
        output_root: str | Path | None = DEFAULT_OUTPUT_ROOT,
        generated_at_utc: datetime | None = None,
    ) -> MonthlyFinancialCloseResult:
        if self.repo is None:
            raise ValueError("MonthlyFinancialCloseService.run requires a repo")
        start_date, end_date = month_to_date_range(month)
        result = self.calculate_from_rows(
            marketplace_id=marketplace_id,
            profile_id=profile_id,
            month=month,
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
                profile_id=profile_id,
                start_date=start_date,
                end_date=end_date,
            ),
            sales_traffic_summary=self.repo.fetch_sales_traffic_period_summary(
                marketplace_id=marketplace_id,
                start_date=start_date,
                end_date=end_date,
            ),
            coupon_summary=self.repo.fetch_coupon_period_summary(
                marketplace_id=marketplace_id,
                start_date=start_date,
                end_date=end_date,
            ),
            promotion_summary=self.repo.fetch_promotion_period_summary(
                marketplace_id=marketplace_id,
                start_date=start_date,
                end_date=end_date,
            ),
            fba_reimbursement_summary=self.repo.fetch_fba_reimbursement_period_summary(
                marketplace_id=marketplace_id,
                start_date=start_date,
                end_date=end_date,
            ),
            generated_at_utc=generated_at_utc,
        )
        if output_root is None:
            return result
        return self.write_report_files(result=result, output_root=output_root)

    def calculate_from_rows(
        self,
        *,
        marketplace_id: str,
        profile_id: str | None,
        month: str,
        start_date: date,
        end_date: date,
        settlement_rows: Iterable[Mapping[str, Any]],
        sku_cost_rows: Iterable[Mapping[str, Any]],
        orders_summary: Mapping[str, Any] | None = None,
        ads_summary: Mapping[str, Any] | None = None,
        sales_traffic_summary: Mapping[str, Any] | None = None,
        coupon_summary: Mapping[str, Any] | None = None,
        promotion_summary: Mapping[str, Any] | None = None,
        fba_reimbursement_summary: Mapping[str, Any] | None = None,
        generated_at_utc: datetime | None = None,
    ) -> MonthlyFinancialCloseResult:
        _validate_period(start_date=start_date, end_date=end_date)
        if month != f"{start_date.year:04d}-{start_date.month:02d}":
            raise ValueError("month must match start_date")
        generated_at = generated_at_utc or datetime.now(UTC).replace(microsecond=0)
        settlement_row_mappings = list(settlement_rows)
        settlement_lines = [
            SettlementProfitLine.from_mapping(row) for row in settlement_row_mappings
        ]
        settlement_lines = [line for line in settlement_lines if not line.is_settlement_summary]
        sku_costs = [SkuCostRecord.from_mapping(row) for row in sku_cost_rows]
        cost_index = _build_cost_index(sku_costs)

        bucket_totals, bucket_counts = _sum_by_bucket(settlement_lines)
        category_totals, category_counts, category_bucket_index = _sum_by_category(
            settlement_lines
        )
        settlement_net_amount = _money(sum((line.amount for line in settlement_lines), ZERO))
        currency = _first_non_empty(line.currency for line in settlement_lines)
        product_sales_amount = _money(
            sum(
                (
                    line.amount
                    for line in settlement_lines
                    if line.amount_category in PRODUCT_SALES_CATEGORIES
                ),
                ZERO,
            )
        )

        sku_accumulator = _build_sku_accumulator(settlement_lines)
        sku_rows: list[MonthlySkuProfitRow] = []
        missing_cost_skus: set[str] = set()
        currency_mismatch_skus: set[str] = set()
        internal_cogs = ZERO
        product_sales_units = 0
        costed_units = 0

        for seller_sku in sorted(sku_accumulator):
            sku_data = sku_accumulator[seller_sku]
            units = int(sku_data["units"])
            sku_product_sales = _money(sku_data["product_sales_amount"])
            sku_settlement_net = _money(sku_data["settlement_net_amount"])
            product_sales_units += units
            sku_cogs, cost_currency, unit_standard_cost, status, notes, costed_sku_units = (
                _calculate_sku_cogs(
                    cost_index=cost_index,
                    marketplace_id=marketplace_id,
                    seller_sku=seller_sku,
                    unit_events=sku_data["unit_events"],
                    settlement_currency=currency,
                )
            )
            if status == "missing_cost":
                missing_cost_skus.add(seller_sku)
            if status == "currency_mismatch":
                currency_mismatch_skus.add(seller_sku)
            costed_units += costed_sku_units
            internal_cogs += sku_cogs
            estimated_profit = _money(sku_settlement_net - sku_cogs)
            sku_rows.append(
                MonthlySkuProfitRow(
                    seller_sku=seller_sku,
                    units=units,
                    product_sales_amount=sku_product_sales,
                    settlement_net_amount=sku_settlement_net,
                    unit_standard_cost=unit_standard_cost,
                    internal_cogs=sku_cogs,
                    estimated_profit_after_cogs=estimated_profit,
                    profit_margin=_safe_ratio(estimated_profit, sku_product_sales),
                    revenue_share=_safe_ratio(sku_product_sales, product_sales_amount),
                    currency=currency,
                    cost_currency=cost_currency,
                    status=status,
                    notes=tuple(notes),
                )
            )

        internal_cogs = _money(internal_cogs)
        estimated_operating_profit = _money(settlement_net_amount - internal_cogs)
        financial_summary = MonthlyFinancialSummary(
            settlement_net_amount=settlement_net_amount,
            product_sales_amount=product_sales_amount,
            product_sales_units=product_sales_units,
            internal_cogs=internal_cogs,
            estimated_operating_profit=estimated_operating_profit,
            profit_margin=_safe_ratio(estimated_operating_profit, product_sales_amount),
            advertising_cost=_money(bucket_totals.get("advertising_cost", ZERO)),
            fba_fee=_money(bucket_totals.get("fba_fee", ZERO)),
            amazon_fee=_money(bucket_totals.get("amazon_fee", ZERO)),
            refund=_money(bucket_totals.get("refund", ZERO)),
            promotion_cost=_money(bucket_totals.get("promotion_cost", ZERO)),
            promotion_fee=_money(bucket_totals.get("promotion_fee", ZERO)),
            reimbursement=_money(bucket_totals.get("reimbursement", ZERO)),
        )
        bucket_rows = _build_bucket_rows(
            bucket_totals=bucket_totals,
            bucket_counts=bucket_counts,
            product_sales_amount=product_sales_amount,
            settlement_net_amount=settlement_net_amount,
        )
        category_rows = _build_category_rows(
            category_totals=category_totals,
            category_counts=category_counts,
            category_bucket_index=category_bucket_index,
        )
        operational_context = _build_operational_context(
            orders_summary=orders_summary or {},
            ads_summary=ads_summary or {},
            sales_traffic_summary=sales_traffic_summary or {},
            coupon_summary=coupon_summary or {},
            promotion_summary=promotion_summary or {},
            fba_reimbursement_summary=fba_reimbursement_summary or {},
            currency=currency,
        )
        reconciliation_checks = _build_reconciliation_checks(
            settlement_net_amount=settlement_net_amount,
            bucket_totals=bucket_totals,
            category_totals=category_totals,
            product_sales_amount=product_sales_amount,
            product_sales_units=product_sales_units,
            costed_units=costed_units,
            missing_cost_skus=missing_cost_skus,
            currency_mismatch_skus=currency_mismatch_skus,
            financial_summary=financial_summary,
            sales_traffic_summary=sales_traffic_summary or {},
            ads_summary=ads_summary or {},
            fba_reimbursement_summary=fba_reimbursement_summary or {},
        )
        warnings = _build_warnings(
            settlement_row_count=len(settlement_lines),
            missing_cost_skus=missing_cost_skus,
            currency_mismatch_skus=currency_mismatch_skus,
            product_sales_units=product_sales_units,
            financial_summary=financial_summary,
            ads_summary=ads_summary or {},
            reconciliation_checks=reconciliation_checks,
        )
        status = _result_status(
            settlement_row_count=len(settlement_lines),
            reconciliation_checks=reconciliation_checks,
        )
        raw_metadata = _build_raw_metadata(
            settlement_lines=settlement_lines,
            raw_settlement_rows=settlement_row_mappings,
            sku_costs=sku_costs,
            orders_summary=orders_summary or {},
            ads_summary=ads_summary or {},
            sales_traffic_summary=sales_traffic_summary or {},
            coupon_summary=coupon_summary or {},
            promotion_summary=promotion_summary or {},
            fba_reimbursement_summary=fba_reimbursement_summary or {},
        )
        return MonthlyFinancialCloseResult(
            marketplace_id=marketplace_id,
            profile_id=profile_id,
            month=month,
            start_date=start_date,
            end_date=end_date,
            generated_at_utc=generated_at,
            status=status,
            currency=currency,
            settlement_row_count=len(settlement_lines),
            financial_summary=financial_summary,
            settlement_bucket_breakdown=tuple(bucket_rows),
            amount_category_breakdown=tuple(category_rows),
            sku_profitability=tuple(sku_rows),
            operational_context=tuple(operational_context),
            reconciliation_checks=tuple(reconciliation_checks),
            warnings=tuple(warnings),
            raw_metadata=raw_metadata,
        )

    def write_report_files(
        self,
        *,
        result: MonthlyFinancialCloseResult,
        output_root: str | Path,
    ) -> MonthlyFinancialCloseResult:
        output_dir = Path(output_root) / result.marketplace_id / result.month
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "monthly_financial_close.json"
        xlsx_path = output_dir / "monthly_financial_close.xlsx"
        output_files = {"json": str(json_path), "xlsx": str(xlsx_path)}
        result_with_paths = result.with_output_files(output_files)
        json_path.write_text(
            json.dumps(
                result_with_paths.to_dict(),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        workbook = build_monthly_financial_close_workbook(result_with_paths)
        workbook.save(xlsx_path)
        return result_with_paths


def month_to_date_range(month: str) -> tuple[date, date]:
    try:
        year_text, month_text = month.split("-", 1)
        year = int(year_text)
        month_number = int(month_text)
        start = date(year, month_number, 1)
    except ValueError as exc:
        raise ValueError("month must be in YYYY-MM format") from exc
    if month_number == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month_number + 1, 1)
    return start, next_month - timedelta(days=1)


def build_monthly_financial_close_workbook(result: MonthlyFinancialCloseResult) -> Workbook:
    workbook = Workbook()
    workbook.remove(workbook.active)
    _write_rows_sheet(workbook, "01_Summary", _summary_rows(result))
    _write_rows_sheet(
        workbook,
        "02_Settlement_Buckets",
        [row.to_dict() for row in result.settlement_bucket_breakdown],
    )
    _write_rows_sheet(
        workbook,
        "03_Amount_Categories",
        [row.to_dict() for row in result.amount_category_breakdown],
    )
    _write_rows_sheet(
        workbook,
        "04_SKU_Profit",
        [_flatten_sku_row(row) for row in result.sku_profitability],
    )
    _write_rows_sheet(
        workbook,
        "05_Operational_Context",
        [metric.to_dict() for metric in result.operational_context],
    )
    _write_rows_sheet(
        workbook,
        "06_Reconciliation_Checks",
        [check.to_dict() for check in result.reconciliation_checks],
    )
    _write_rows_sheet(workbook, "07_Warnings", [warning.to_dict() for warning in result.warnings])
    _write_rows_sheet(workbook, "08_Raw_Metadata", _metadata_rows(result))
    workbook.active = 0
    return workbook


def _summary_rows(result: MonthlyFinancialCloseResult) -> list[dict[str, Any]]:
    fs = result.financial_summary
    return [
        _metric_row("Report Type", REPORT_TYPE, None, "Monthly Financial Close Report v1"),
        _metric_row("Marketplace ID", result.marketplace_id, None, ""),
        _metric_row(
            "Ads Profile ID",
            result.profile_id or "",
            None,
            "Used only for Ads API context.",
        ),
        _metric_row("Month", result.month, None, "Natural calendar month."),
        _metric_row("Period Start", result.start_date.isoformat(), None, "Inclusive."),
        _metric_row("Period End", result.end_date.isoformat(), None, "Inclusive."),
        _metric_row("Status", result.status, None, "ok / needs_review / no_data."),
        _metric_row("Currency", result.currency or "", None, "Settlement currency."),
        _metric_row("Settlement Rows", result.settlement_row_count, None, "Non-summary rows."),
        _metric_row(
            "Settlement Net Amount",
            fs.settlement_net_amount,
            result.currency,
            "Financial source of truth.",
        ),
        _metric_row(
            "Product Sales Amount",
            fs.product_sales_amount,
            result.currency,
            "Settlement product-sales categories.",
        ),
        _metric_row(
            "Product Sales Units",
            fs.product_sales_units,
            None,
            "Deduplicated by settlement/order/item/SKU.",
        ),
        _metric_row(
            "Internal COGS",
            fs.internal_cogs,
            result.currency,
            "SKU standard cost from amazon_sku_cost.",
        ),
        _metric_row(
            "Estimated Operating Profit",
            fs.estimated_operating_profit,
            result.currency,
            "Settlement net minus internal COGS.",
        ),
        _metric_row("Profit Margin", fs.profit_margin, None, "Estimated profit / product sales."),
        _metric_row(
            "Advertising Cost",
            fs.advertising_cost,
            result.currency,
            "Settlement advertising bucket.",
        ),
        _metric_row("FBA Fee", fs.fba_fee, result.currency, "Settlement FBA bucket."),
        _metric_row("Amazon Fee", fs.amazon_fee, result.currency, "Settlement Amazon fee bucket."),
        _metric_row("Refund", fs.refund, result.currency, "Settlement refund bucket."),
        _metric_row(
            "Promotion Cost",
            fs.promotion_cost,
            result.currency,
            "Settlement promotion cost bucket.",
        ),
        _metric_row(
            "Promotion Fee",
            fs.promotion_fee,
            result.currency,
            "Settlement promotion fee bucket.",
        ),
        _metric_row(
            "Reimbursement",
            fs.reimbursement,
            result.currency,
            "Settlement reimbursement bucket.",
        ),
        _metric_row(
            "SKU Profit Table Scope",
            "Before account-level expense allocation",
            None,
            SKU_PROFIT_SCOPE_NOTE,
        ),
    ]


def _metric_row(metric: str, value: Any, currency: str | None, notes: str) -> dict[str, Any]:
    return {"metric": metric, "value": _xlsx_value(value), "currency": currency, "notes": notes}


def _metadata_rows(result: MonthlyFinancialCloseResult) -> list[dict[str, Any]]:
    rows = [
        {"key": "report_type", "value": REPORT_TYPE},
        {"key": "version", "value": REPORT_VERSION},
        {"key": "marketplace_id", "value": result.marketplace_id},
        {"key": "profile_id", "value": result.profile_id or ""},
        {"key": "month", "value": result.month},
        {"key": "generated_at_utc", "value": result.generated_at_utc.isoformat()},
    ]
    for key, value in sorted(result.raw_metadata.items()):
        rows.append({"key": key, "value": _json_value(value)})
    return rows


def _flatten_sku_row(row: MonthlySkuProfitRow) -> dict[str, Any]:
    payload = row.to_dict()
    payload["notes"] = "; ".join(row.notes)
    payload["scope_note"] = SKU_PROFIT_SCOPE_NOTE
    return payload


def _write_rows_sheet(
    workbook: Workbook,
    sheet_name: str,
    rows: Sequence[Mapping[str, Any]],
) -> None:
    sheet = workbook.create_sheet(sheet_name)
    if rows:
        headers = list(rows[0].keys())
    else:
        headers = ["message"]
        rows = [{"message": "No rows"}]
    sheet.append(headers)
    for row in rows:
        sheet.append([_xlsx_value(row.get(header)) for header in headers])
    _format_sheet(sheet)


def _format_sheet(sheet: Any) -> None:
    header_fill = PatternFill("solid", fgColor="1F4E78")
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            header = sheet.cell(row=1, column=cell.column).value
            if isinstance(cell.value, int | float) and header:
                header_text = str(header)
                if "share" in header_text or "margin" in header_text or "pct" in header_text:
                    cell.number_format = "0.00%"
                elif "amount" in header_text or "cost" in header_text or "cogs" in header_text:
                    cell.number_format = "#,##0.00"
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column_cells in sheet.columns:
        header = str(column_cells[0].value or "")
        max_len = min(max(len(str(cell.value or "")) for cell in column_cells), 60)
        width = max(12, min(max_len + 2, 42))
        if header in {"message", "notes"}:
            width = 60
        if header in {"seller_sku", "metric", "check_name", "warning_code"}:
            width = max(width, 24)
        sheet.column_dimensions[column_cells[0].column_letter].width = width


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
                "unit_events": [],
            },
        )
        data["settlement_net_amount"] += line.amount
        if line.amount_category in PRODUCT_SALES_CATEGORIES:
            data["product_sales_amount"] += line.amount
            unit_key = _unit_dedupe_key(line)
            if unit_key not in seen_unit_keys:
                seen_unit_keys.add(unit_key)
                quantity = max(0, line.quantity_purchased or 0)
                data["units"] += quantity
                if quantity > 0:
                    data["unit_events"].append(
                        {"posted_date": line.posted_date, "quantity": quantity}
                    )
    return accumulator


def _unit_dedupe_key(line: SettlementProfitLine) -> tuple[Any, ...]:
    if line.order_item_code:
        return (line.settlement_id, line.order_id, line.order_item_code, line.seller_sku)
    return (line.settlement_id, line.order_id, line.seller_sku, line.id)


def _calculate_sku_cogs(
    *,
    cost_index: Mapping[tuple[str, str], Sequence[SkuCostRecord]],
    marketplace_id: str,
    seller_sku: str,
    unit_events: Sequence[Mapping[str, Any]],
    settlement_currency: str | None,
) -> tuple[Decimal, str | None, Decimal | None, str, list[str], int]:
    candidates = cost_index.get((marketplace_id, seller_sku), ())
    if not candidates:
        units = sum(_optional_int(event.get("quantity")) or 0 for event in unit_events)
        return ZERO, None, None, "missing_cost", ["no amazon_sku_cost row"], 0 if units else 0
    if not unit_events:
        return ZERO, candidates[0].currency, None, "ok", ["no product-sales units"], 0

    cogs = ZERO
    costed_units = 0
    matched_costs: list[SkuCostRecord] = []
    notes: list[str] = []
    status = "ok"
    cost_currency: str | None = None
    for event in unit_events:
        quantity = _optional_int(event.get("quantity")) or 0
        posted_date = event.get("posted_date")
        if posted_date is None:
            match = candidates[0]
            notes.append("missing posted_date; used latest cost row")
        else:
            match = next((cost for cost in candidates if cost.is_effective_on(posted_date)), None)
        if match is None:
            status = "missing_cost"
            notes.append(f"no effective cost for posted date {posted_date}")
            continue
        cost_currency = cost_currency or match.currency
        matched_costs.append(match)
        cogs += match.unit_standard_cost * Decimal(quantity)
        costed_units += quantity
        if settlement_currency and match.currency and match.currency != settlement_currency:
            status = "currency_mismatch"
            notes.append(
                f"cost currency {match.currency} != settlement currency {settlement_currency}"
            )

    if not matched_costs:
        return ZERO, cost_currency, None, "missing_cost", notes, costed_units
    unique_cost_keys = {
        (
            cost.effective_from,
            cost.effective_to,
            cost.currency,
            cost.unit_standard_cost,
        )
        for cost in matched_costs
    }
    if len(unique_cost_keys) > 1:
        notes.append("multiple cost rows matched; weighted average unit_standard_cost shown")
    if status == "missing_cost":
        return _money(cogs), cost_currency, None, status, notes, costed_units
    unit_standard_cost = _money(cogs / Decimal(costed_units)) if costed_units else None
    return _money(cogs), cost_currency, unit_standard_cost, status, notes, costed_units


def _build_cost_index(costs: Iterable[SkuCostRecord]) -> dict[tuple[str, str], list[SkuCostRecord]]:
    index: dict[tuple[str, str], list[SkuCostRecord]] = defaultdict(list)
    for cost in costs:
        index[(cost.marketplace_id, cost.seller_sku)].append(cost)
    for rows in index.values():
        rows.sort(key=lambda cost: cost.effective_from, reverse=True)
    return dict(index)


def _sum_by_bucket(
    settlement_lines: Iterable[SettlementProfitLine],
) -> tuple[dict[str, Decimal], dict[str, int]]:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    counts: dict[str, int] = defaultdict(int)
    for line in settlement_lines:
        key = str(line.profit_bucket or "unknown")
        totals[key] += line.amount
        counts[key] += 1
    return dict(totals), dict(counts)


def _sum_by_category(
    settlement_lines: Iterable[SettlementProfitLine],
) -> tuple[dict[str, Decimal], dict[str, int], dict[str, set[str]]]:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    counts: dict[str, int] = defaultdict(int)
    bucket_index: dict[str, set[str]] = defaultdict(set)
    for line in settlement_lines:
        key = str(line.amount_category or "unknown")
        totals[key] += line.amount
        counts[key] += 1
        bucket_index[key].add(str(line.profit_bucket or "unknown"))
    return dict(totals), dict(counts), dict(bucket_index)


def _build_bucket_rows(
    *,
    bucket_totals: Mapping[str, Decimal],
    bucket_counts: Mapping[str, int],
    product_sales_amount: Decimal,
    settlement_net_amount: Decimal,
) -> list[SettlementBucketBreakdownRow]:
    rows = []
    for bucket, amount in sorted(bucket_totals.items()):
        notes = "needs review" if bucket in REVIEW_BUCKETS and amount != ZERO else ""
        rows.append(
            SettlementBucketBreakdownRow(
                profit_bucket=bucket,
                amount=_money(amount),
                row_count=bucket_counts.get(bucket, 0),
                share_of_product_sales=_safe_ratio(amount, product_sales_amount),
                share_of_settlement_net=_safe_ratio(amount, settlement_net_amount),
                notes=notes,
            )
        )
    return rows


def _build_category_rows(
    *,
    category_totals: Mapping[str, Decimal],
    category_counts: Mapping[str, int],
    category_bucket_index: Mapping[str, set[str]],
) -> list[AmountCategoryBreakdownRow]:
    rows = []
    for category, amount in sorted(category_totals.items()):
        buckets = sorted(category_bucket_index.get(category, set()))
        bucket = buckets[0] if len(buckets) == 1 else "mixed"
        notes = "needs review" if category in REVIEW_CATEGORIES and amount != ZERO else ""
        rows.append(
            AmountCategoryBreakdownRow(
                amount_category=category,
                profit_bucket=bucket,
                amount=_money(amount),
                row_count=category_counts.get(category, 0),
                notes=notes,
            )
        )
    return rows


def _build_operational_context(
    *,
    orders_summary: Mapping[str, Any],
    ads_summary: Mapping[str, Any],
    sales_traffic_summary: Mapping[str, Any],
    coupon_summary: Mapping[str, Any],
    promotion_summary: Mapping[str, Any],
    fba_reimbursement_summary: Mapping[str, Any],
    currency: str | None,
) -> list[OperationalMetric]:
    order_currency = _empty_to_none(orders_summary.get("currency")) or currency
    sales_currency = (
        _empty_to_none(sales_traffic_summary.get("ordered_product_sales_currency"))
        or currency
    )
    coupon_currency = _empty_to_none(coupon_summary.get("coupon_currency")) or currency
    promotion_currency = _empty_to_none(promotion_summary.get("promotion_currency")) or currency
    reimbursement_currency = (
        _empty_to_none(fba_reimbursement_summary.get("reimbursement_currency"))
        or currency
    )
    metrics: list[OperationalMetric] = []

    def add(
        group: str,
        name: str,
        value: Decimal | int | str | None,
        metric_currency: str | None,
        source: str,
        notes: str = "",
    ) -> None:
        metrics.append(OperationalMetric(group, name, value, metric_currency, source, notes))

    add(
        "Orders",
        "order_count",
        _int_metric(orders_summary, "order_count"),
        None,
        "amazon_order_item",
    )
    add(
        "Orders",
        "order_item_rows",
        _int_metric(orders_summary, "order_item_rows"),
        None,
        "amazon_order_item",
    )
    add(
        "Orders",
        "ordered_units",
        _int_metric(orders_summary, "ordered_units"),
        None,
        "amazon_order_item",
    )
    add(
        "Orders",
        "ordered_item_sales_amount",
        _to_decimal(orders_summary.get("ordered_item_sales_amount")),
        order_currency,
        "amazon_order_item",
    )
    add(
        "Orders",
        "item_promotion_discount_amount",
        _to_decimal(orders_summary.get("item_promotion_discount_amount")),
        order_currency,
        "amazon_order_item",
    )
    add(
        "Orders",
        "ship_promotion_discount_amount",
        _to_decimal(orders_summary.get("ship_promotion_discount_amount")),
        order_currency,
        "amazon_order_item",
    )
    add(
        "Orders",
        "order_exception_count",
        _int_metric(orders_summary, "order_exception_count"),
        None,
        "amazon_order_item",
        "Cancelled/Canceled rows only in v1.",
    )

    add(
        "Sales & Traffic",
        "units_ordered",
        _int_metric(sales_traffic_summary, "units_ordered"),
        None,
        "amazon_sales_traffic_daily",
    )
    add(
        "Sales & Traffic",
        "ordered_product_sales_amount",
        _to_decimal(sales_traffic_summary.get("ordered_product_sales_amount")),
        sales_currency,
        "amazon_sales_traffic_daily",
    )
    add(
        "Sales & Traffic",
        "sessions",
        _int_metric(sales_traffic_summary, "sessions"),
        None,
        "amazon_sales_traffic_daily",
    )
    add(
        "Sales & Traffic",
        "page_views",
        _int_metric(sales_traffic_summary, "page_views"),
        None,
        "amazon_sales_traffic_daily",
    )
    add(
        "Sales & Traffic",
        "total_order_items",
        _int_metric(sales_traffic_summary, "total_order_items"),
        None,
        "amazon_sales_traffic_daily",
    )
    add(
        "Sales & Traffic",
        "units_refunded",
        _int_metric(sales_traffic_summary, "units_refunded"),
        None,
        "amazon_sales_traffic_daily",
    )
    add(
        "Sales & Traffic",
        "unit_session_rate",
        _safe_ratio(
            _to_decimal(sales_traffic_summary.get("units_ordered")),
            _to_decimal(sales_traffic_summary.get("sessions")),
        ),
        None,
        "derived",
        "units_ordered / sessions",
    )
    add(
        "Sales & Traffic",
        "sales_per_session",
        _safe_ratio(
            _to_decimal(sales_traffic_summary.get("ordered_product_sales_amount")),
            _to_decimal(sales_traffic_summary.get("sessions")),
        ),
        sales_currency,
        "derived",
        "ordered_product_sales_amount / sessions",
    )

    add(
        "Ads API",
        "ads_cost",
        _to_decimal(ads_summary.get("ads_cost")),
        currency,
        "amazon_ads_sp_campaign_daily",
        "Report-date Ads API context; not financial source of truth.",
    )
    add(
        "Ads API",
        "ads_sales_7d",
        _to_decimal(ads_summary.get("ads_sales_7d")),
        currency,
        "amazon_ads_sp_campaign_daily",
    )
    for name in ("ads_clicks", "ads_impressions", "ads_purchases_7d", "ads_row_count"):
        add("Ads API", name, _int_metric(ads_summary, name), None, "amazon_ads_sp_campaign_daily")

    add(
        "Coupon",
        "coupon_count",
        _int_metric(coupon_summary, "coupon_count"),
        None,
        "amazon_coupon_performance",
        "Overlapping campaign period.",
    )
    for name in ("coupon_clips", "coupon_redemptions"):
        add("Coupon", name, _int_metric(coupon_summary, name), None, "amazon_coupon_performance")
    for name in ("coupon_total_discount", "coupon_budget_spent", "coupon_sales"):
        add(
            "Coupon",
            name,
            _to_decimal(coupon_summary.get(name)),
            coupon_currency,
            "amazon_coupon_performance",
        )

    add(
        "Promotion",
        "promotion_count",
        _int_metric(promotion_summary, "promotion_count"),
        None,
        "amazon_promotion_performance",
        "Overlapping campaign period.",
    )
    for name in ("promotion_glance_views", "promotion_units_sold"):
        add(
            "Promotion",
            name,
            _int_metric(promotion_summary, name),
            None,
            "amazon_promotion_performance",
        )
    add(
        "Promotion",
        "promotion_revenue",
        _to_decimal(promotion_summary.get("promotion_revenue")),
        promotion_currency,
        "amazon_promotion_performance",
    )

    add(
        "FBA Reimbursements",
        "reimbursement_count",
        _int_metric(fba_reimbursement_summary, "reimbursement_count"),
        None,
        "amazon_fba_reimbursement",
    )
    add(
        "FBA Reimbursements",
        "reimbursement_report_amount",
        _to_decimal(fba_reimbursement_summary.get("reimbursement_report_amount")),
        reimbursement_currency,
        "amazon_fba_reimbursement",
    )
    for name in ("reimbursement_quantity", "reimbursement_reason_count"):
        add(
            "FBA Reimbursements",
            name,
            _int_metric(fba_reimbursement_summary, name),
            None,
            "amazon_fba_reimbursement",
        )
    return metrics


def _build_reconciliation_checks(
    *,
    settlement_net_amount: Decimal,
    bucket_totals: Mapping[str, Decimal],
    category_totals: Mapping[str, Decimal],
    product_sales_amount: Decimal,
    product_sales_units: int,
    costed_units: int,
    missing_cost_skus: set[str],
    currency_mismatch_skus: set[str],
    financial_summary: MonthlyFinancialSummary,
    sales_traffic_summary: Mapping[str, Any],
    ads_summary: Mapping[str, Any],
    fba_reimbursement_summary: Mapping[str, Any],
) -> list[ReconciliationCheck]:
    checks = []
    bucket_sum = _money(sum(bucket_totals.values(), ZERO))
    checks.append(
        _money_check("settlement_bucket_sum_matches_net", settlement_net_amount, bucket_sum)
    )
    category_sum = _money(sum(category_totals.values(), ZERO))
    checks.append(
        _money_check("amount_category_sum_matches_net", settlement_net_amount, category_sum)
    )
    checks.append(
        ReconciliationCheck(
            check_name="sku_cost_coverage",
            status="ok" if costed_units == product_sales_units else "needs_review",
            severity="error" if costed_units != product_sales_units else "info",
            expected=str(product_sales_units),
            actual=str(costed_units),
            diff=str(product_sales_units - costed_units),
            message="Product-sales units with matched amazon_sku_cost.",
        )
    )
    checks.append(
        ReconciliationCheck(
            check_name="missing_cost_skus",
            status="ok" if not missing_cost_skus else "needs_review",
            severity="error" if missing_cost_skus else "info",
            expected="none",
            actual=", ".join(sorted(missing_cost_skus)) if missing_cost_skus else "none",
            message="Missing SKU cost must be reviewed; report does not silently assume zero cost.",
        )
    )
    checks.append(
        ReconciliationCheck(
            check_name="currency_mismatch_skus",
            status="ok" if not currency_mismatch_skus else "needs_review",
            severity="error" if currency_mismatch_skus else "info",
            expected="none",
            actual=", ".join(sorted(currency_mismatch_skus)) if currency_mismatch_skus else "none",
            message="SKU cost currency should match settlement currency in v1.",
        )
    )
    unknown_bucket_amount = _money(sum(bucket_totals.get(key, ZERO) for key in REVIEW_BUCKETS))
    checks.append(_zero_review_check("unknown_bucket_amount", unknown_bucket_amount))
    unknown_category_amount = _money(
        sum(category_totals.get(key, ZERO) for key in REVIEW_CATEGORIES)
    )
    checks.append(_zero_review_check("unclassified_amount", unknown_category_amount))
    tax_passthrough = _money(bucket_totals.get("tax_passthrough", ZERO))
    checks.append(
        ReconciliationCheck(
            check_name="tax_passthrough_net",
            status="ok" if tax_passthrough == ZERO else "warning",
            severity="warning" if tax_passthrough != ZERO else "info",
            expected="0.00",
            actual=_decimal_to_string(tax_passthrough),
            diff=_decimal_to_string(tax_passthrough),
            message="Tax passthrough should normally be reviewed but does not change core formula.",
        )
    )
    sales_traffic_sales = _to_decimal(sales_traffic_summary.get("ordered_product_sales_amount"))
    checks.append(
        _context_diff_check(
            "settlement_product_sales_vs_sales_traffic",
            expected=product_sales_amount,
            actual=sales_traffic_sales,
            message=(
                "Settlement posted-date product sales versus Sales & Traffic report-date sales. "
                "Timing differences are expected."
            ),
        )
    )
    settlement_ads_abs = abs(financial_summary.advertising_cost)
    ads_api_spend = _to_decimal(ads_summary.get("ads_cost"))
    checks.append(
        _context_diff_check(
            "settlement_ads_fee_vs_ads_api_spend",
            expected=settlement_ads_abs,
            actual=ads_api_spend,
            message=(
                "Settlement advertising fee and Ads API report-date spend use different timing "
                "and should not be forced to tie."
            ),
        )
    )
    reimbursement_report_amount = _to_decimal(
        fba_reimbursement_summary.get("reimbursement_report_amount")
    )
    checks.append(
        _context_diff_check(
            "settlement_reimbursement_vs_fba_reimbursement_report",
            expected=financial_summary.reimbursement,
            actual=reimbursement_report_amount,
            message="Settlement reimbursement versus FBA Reimbursements report context.",
        )
    )
    return checks


def _money_check(name: str, expected: Decimal, actual: Decimal) -> ReconciliationCheck:
    diff = _money(actual - expected)
    return ReconciliationCheck(
        check_name=name,
        status="ok" if diff == ZERO else "needs_review",
        severity="error" if diff != ZERO else "info",
        expected=_decimal_to_string(expected),
        actual=_decimal_to_string(actual),
        diff=_decimal_to_string(diff),
        message="Settlement aggregation self-check.",
    )


def _zero_review_check(name: str, amount: Decimal) -> ReconciliationCheck:
    return ReconciliationCheck(
        check_name=name,
        status="ok" if amount == ZERO else "needs_review",
        severity="error" if amount != ZERO else "info",
        expected="0.00",
        actual=_decimal_to_string(amount),
        diff=_decimal_to_string(amount),
        message="Non-zero unknown/unclassified amount should be reviewed before sharing.",
    )


def _context_diff_check(
    name: str,
    *,
    expected: Decimal,
    actual: Decimal,
    message: str,
) -> ReconciliationCheck:
    diff = _money(actual - expected)
    diff_pct = _optional_ratio_to_string(_safe_ratio(diff, expected))
    if expected == ZERO and actual == ZERO:
        status = "ok"
        severity = "info"
    else:
        status = "warning"
        severity = "warning"
    return ReconciliationCheck(
        check_name=name,
        status=status,
        severity=severity,
        expected=_decimal_to_string(expected),
        actual=_decimal_to_string(actual),
        diff=_decimal_to_string(diff),
        diff_pct=diff_pct,
        message=message,
    )


def _build_warnings(
    *,
    settlement_row_count: int,
    missing_cost_skus: set[str],
    currency_mismatch_skus: set[str],
    product_sales_units: int,
    financial_summary: MonthlyFinancialSummary,
    ads_summary: Mapping[str, Any],
    reconciliation_checks: Sequence[ReconciliationCheck],
) -> list[WarningEntry]:
    warnings = []
    if settlement_row_count == 0:
        warnings.append(
            WarningEntry(
                "no_settlement_rows",
                "error",
                "No settlement rows found for this marketplace/month.",
                related_source="amazon_settlement_transaction",
            )
        )
    if product_sales_units == 0 and settlement_row_count > 0:
        warnings.append(
            WarningEntry(
                "no_product_sales_units",
                "warning",
                "No product-sales units found; SKU COGS may be zero for this period.",
                related_source="amazon_settlement_transaction",
            )
        )
    for sku in sorted(missing_cost_skus):
        warnings.append(
            WarningEntry(
                "missing_sku_cost",
                "error",
                "Missing amazon_sku_cost row or effective cost date.",
                related_sku=sku,
                related_source="amazon_sku_cost",
            )
        )
    for sku in sorted(currency_mismatch_skus):
        warnings.append(
            WarningEntry(
                "currency_mismatch",
                "error",
                "SKU cost currency differs from settlement currency.",
                related_sku=sku,
                related_source="amazon_sku_cost",
            )
        )
    ads_row_count = _optional_int(ads_summary.get("ads_row_count")) or 0
    ads_api_spend = _to_decimal(ads_summary.get("ads_cost"))
    if (
        abs(financial_summary.advertising_cost) != ZERO
        and ads_row_count == 0
        and ads_api_spend == ZERO
    ):
        warnings.append(
            WarningEntry(
                "ads_api_context_missing",
                "warning",
                (
                    "Settlement has advertising fees but Ads API campaign daily context has "
                    "zero rows for this period/profile. This affects operational context only; "
                    "financial profit remains Settlement-led."
                ),
                related_source="amazon_ads_sp_campaign_daily",
            )
        )
    for check in reconciliation_checks:
        if check.status == "needs_review" and check.check_name not in {
            "missing_cost_skus",
            "currency_mismatch_skus",
        }:
            warnings.append(
                WarningEntry(
                    check.check_name,
                    check.severity,
                    check.message,
                    related_source="reconciliation_checks",
                )
            )
    warnings.append(
        WarningEntry(
            "settlement_led_policy",
            "info",
            SETTLEMENT_LED_POLICY_NOTE,
        )
    )
    return warnings


def _result_status(
    *,
    settlement_row_count: int,
    reconciliation_checks: Sequence[ReconciliationCheck],
) -> str:
    if settlement_row_count == 0:
        return "no_data"
    if any(check.status == "needs_review" for check in reconciliation_checks):
        return "needs_review"
    return "ok"


def _build_raw_metadata(
    *,
    settlement_lines: Sequence[SettlementProfitLine],
    raw_settlement_rows: Sequence[Mapping[str, Any]],
    sku_costs: Sequence[SkuCostRecord],
    orders_summary: Mapping[str, Any],
    ads_summary: Mapping[str, Any],
    sales_traffic_summary: Mapping[str, Any],
    coupon_summary: Mapping[str, Any],
    promotion_summary: Mapping[str, Any],
    fba_reimbursement_summary: Mapping[str, Any],
) -> dict[str, Any]:
    settlement_ids = sorted({line.settlement_id for line in settlement_lines if line.settlement_id})
    source_report_ids = sorted(
        {
            str(row.get("source_report_id"))
            for row in raw_settlement_rows
            if row.get("source_report_id")
        }
    )
    source_raw_file_paths = sorted(
        {
            str(row.get("source_raw_file_path"))
            for row in raw_settlement_rows
            if row.get("source_raw_file_path")
        }
    )
    return {
        "settlement_id_count": len(settlement_ids),
        "settlement_ids": settlement_ids,
        "settlement_source_report_id_count": len(source_report_ids),
        "settlement_source_report_ids": source_report_ids,
        "settlement_source_raw_file_path_count": len(source_raw_file_paths),
        "settlement_source_raw_file_paths": source_raw_file_paths,
        "sku_cost_rows_loaded": len(sku_costs),
        "orders_summary_row_count": _optional_int(orders_summary.get("order_item_rows")) or 0,
        "ads_summary_row_count": _optional_int(ads_summary.get("ads_row_count")) or 0,
        "sales_traffic_summary_row_count": _optional_int(
            sales_traffic_summary.get("sales_traffic_row_count")
        )
        or 0,
        "coupon_count": _optional_int(coupon_summary.get("coupon_count")) or 0,
        "promotion_count": _optional_int(promotion_summary.get("promotion_count")) or 0,
        "reimbursement_count": _optional_int(
            fba_reimbursement_summary.get("reimbursement_count")
        )
        or 0,
    }


def _validate_period(*, start_date: date, end_date: date) -> None:
    if end_date < start_date:
        raise ValueError("end_date must be >= start_date")


def _int_metric(values: Mapping[str, Any], key: str) -> int:
    return _optional_int(values.get(key)) or 0


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


def _ratio(value: Decimal) -> Decimal:
    return value.quantize(RATIO_QUANT, rounding=ROUND_HALF_UP)


def _safe_ratio(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator == ZERO:
        return None
    return _ratio(numerator / denominator)


def _decimal_to_string(value: Decimal) -> str:
    return str(_money(value))


def _optional_decimal_to_string(value: Decimal | None) -> str | None:
    return None if value is None else _decimal_to_string(value)


def _optional_ratio_to_string(value: Decimal | None) -> str | None:
    return None if value is None else str(_ratio(value))


def _format_money(value: Decimal, currency: str | None) -> str:
    prefix = f"{currency} " if currency else ""
    return f"{prefix}{_decimal_to_string(value)}"


def _format_ratio(value: Decimal) -> str:
    return f"{(value * Decimal('100')).quantize(Decimal('0.01'))}%"


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return _decimal_to_string(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value


def _json_safe_mapping(values: Mapping[str, Any]) -> dict[str, Any]:
    return {key: _json_value(value) for key, value in values.items()}


def _xlsx_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, list | tuple | set):
        return json.dumps(list(value), ensure_ascii=False)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


__all__ = [
    "DEFAULT_OUTPUT_ROOT",
    "MonthlyFinancialCloseResult",
    "MonthlyFinancialCloseService",
    "MonthlyFinancialSummary",
    "MonthlySkuProfitRow",
    "OperationalMetric",
    "ReconciliationCheck",
    "SettlementBucketBreakdownRow",
    "WarningEntry",
    "build_monthly_financial_close_workbook",
    "month_to_date_range",
]
