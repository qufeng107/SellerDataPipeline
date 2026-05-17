from __future__ import annotations

from dataclasses import dataclass, field

from seller_data_pipeline.integrations.amazon import report_types as rt


@dataclass(frozen=True)
class ReportSamplingPlanItem:
    """One Amazon report sampling target.

    mode is "request" for createReport or "discover" for Amazon-generated reports.
    sensitive means the report can contain buyer/customer-identifying fields or comments.
    """

    report_type: str
    mode: str
    label: str
    purpose: str
    days: int | None = None
    report_options: dict[str, str] = field(default_factory=dict)
    priority: int = 100
    sensitive: bool = False
    notes: str = ""

    def operation_key(self) -> str:
        option_part = ",".join(
            f"{key}={value}" for key, value in sorted(self.report_options.items())
        )
        return f"{self.mode}:{self.report_type}:{self.days}:{option_part}"


CORE_SAMPLING_PLAN: tuple[ReportSamplingPlanItem, ...] = (
    ReportSamplingPlanItem(
        report_type=rt.LISTINGS_ALL_DATA,
        mode="request",
        label="All listing data",
        purpose="SKU, ASIN, listing status, price, title, fulfillment channel.",
        priority=10,
        notes="Already sampled once; keep in the plan for reproducible fresh snapshots.",
    ),
    ReportSamplingPlanItem(
        report_type=rt.INVENTORY,
        mode="request",
        label="FBA Manage Inventory",
        purpose="FBA sellable, unsellable, reserved, inbound, and warehouse quantities.",
        priority=20,
    ),
    ReportSamplingPlanItem(
        report_type=rt.SALES_AND_TRAFFIC,
        mode="request",
        label="Sales and traffic, 7 days",
        purpose="Daily and ASIN-level sales, sessions, page views, conversion rate.",
        days=7,
        priority=30,
    ),
    ReportSamplingPlanItem(
        report_type=rt.ALL_ORDERS_BY_ORDER_DATE,
        mode="request",
        label="All orders by order date, 30 days",
        purpose="Order/item-level revenue, quantity, order status, promotions, and channel.",
        days=30,
        priority=40,
        notes="Amazon limits order-tracking report date ranges to 30 days.",
    ),
    ReportSamplingPlanItem(
        report_type=rt.RETURNS_BY_RETURN_DATE,
        mode="request",
        label="Returns by return date, 60 days",
        purpose="Return requests, ASIN, reason codes, RMA, and return status.",
        days=60,
        priority=50,
    ),
    ReportSamplingPlanItem(
        report_type=rt.FBA_CUSTOMER_RETURNS,
        mode="request",
        label="FBA customer returns, 60 days",
        purpose="FBA received returns, disposition, reason, status, and customer comments.",
        days=60,
        priority=60,
        sensitive=True,
        notes="May include customer comments. Excluded unless --include-sensitive is used.",
    ),
    ReportSamplingPlanItem(
        report_type=rt.FBA_REIMBURSEMENTS,
        mode="request",
        label="FBA reimbursements, 90 days",
        purpose="Inventory reimbursements, case IDs, reasons, cash and inventory quantities.",
        days=90,
        priority=70,
    ),
    ReportSamplingPlanItem(
        report_type=rt.FBA_ESTIMATED_FEES,
        mode="request",
        label="FBA estimated fee preview",
        purpose="Estimated referral fee and FBA fulfillment fee per SKU/FNSKU/ASIN.",
        days=4,
        priority=80,
        notes="Amazon requires dataStartTime at least 72 hours before now; sample uses 4 days.",
    ),
    ReportSamplingPlanItem(
        report_type=rt.FBA_STORAGE_FEES,
        mode="request",
        label="FBA monthly storage fee charges",
        purpose="Monthly storage fee estimate, average quantity, volume, and size tier.",
        days=31,
        priority=90,
    ),
    ReportSamplingPlanItem(
        report_type=rt.FBA_INVENTORY_PLANNING,
        mode="request",
        label="FBA inventory planning / inventory health",
        purpose="Inventory age, sell-through, days of supply, excess quantity, action advice.",
        priority=100,
    ),
    ReportSamplingPlanItem(
        report_type=rt.LEDGER_SUMMARY_VIEW,
        mode="request",
        label="Inventory ledger summary, 30 days",
        purpose="Warehouse inventory movements: receipts, shipments, returns, lost/found/damaged.",
        days=30,
        report_options={"aggregateByLocation": "COUNTRY", "aggregatedByTimePeriod": "DAILY"},
        priority=110,
        notes="If Amazon rejects reportOptions for the account, retry manually without options.",
    ),
    ReportSamplingPlanItem(
        report_type=rt.LEDGER_DETAIL_VIEW,
        mode="request",
        label="Inventory ledger detail, 30 days",
        purpose="Detailed FBA warehouse movement events for reconciliation and shrinkage analysis.",
        days=30,
        priority=120,
        notes=(
            "Amazon docs describe empty eventType as default, but the current SP-API "
            "validation rejected an explicit empty string. Retry without reportOptions."
        ),
    ),
    ReportSamplingPlanItem(
        report_type=rt.RESERVED_INVENTORY,
        mode="request",
        label="FBA reserved inventory",
        purpose="Reserved units split by customer orders, FC transfers, and FC processing.",
        priority=121,
    ),
    ReportSamplingPlanItem(
        report_type=rt.RESTOCK_INVENTORY,
        mode="request",
        label="Restock inventory recommendations",
        purpose="Restock recommendation, days of supply, inbound and available quantities.",
        priority=122,
    ),
    ReportSamplingPlanItem(
        report_type=rt.STRANDED_INVENTORY,
        mode="request",
        label="FBA stranded inventory",
        purpose="Stranded inventory status and recommended actions if any SKU is stranded.",
        priority=123,
    ),
    ReportSamplingPlanItem(
        report_type=rt.FBA_RECOMMENDED_REMOVAL,
        mode="request",
        label="FBA recommended removal",
        purpose="Sellable/unsellable aging and recommended removal quantities.",
        priority=124,
    ),
    ReportSamplingPlanItem(
        report_type=rt.FBA_LONG_TERM_STORAGE_FEES,
        mode="request",
        label="FBA long-term storage fee charges",
        purpose="Long-term storage fee charges when applicable.",
        days=31,
        priority=125,
        notes="May return cancelled/no-data if the account has no LTSF charges in the window.",
    ),
    ReportSamplingPlanItem(
        report_type=rt.FBA_OVERAGE_FEES,
        mode="request",
        label="FBA overage fee charges",
        purpose="Storage limit overage fee charges when applicable.",
        days=31,
        priority=126,
        notes="May return cancelled/no-data if the account has no overage fee charges.",
    ),
    ReportSamplingPlanItem(
        report_type=rt.SETTLEMENT_V2,
        mode="discover",
        label="Settlement V2 reports, 89 days",
        purpose=(
            "Actual financial ledger: sales, fees, refunds, reimbursements, ads, coupons, deals."
        ),
        days=89,
        priority=130,
        notes="Amazon-generated only; discover with getReports instead of createReport.",
    ),
    ReportSamplingPlanItem(
        report_type=rt.PROMOTION_PERFORMANCE,
        mode="request",
        label="Promotion performance, 89 days",
        purpose="Promotion/discount performance if available for the seller account.",
        days=89,
        report_options={
            "promotionStartDateFrom": "{data_start_time}",
            "promotionStartDateTo": "{data_end_time}",
        },
        priority=140,
        notes=(
            "Diagnostic sampling showed this report requires reportOptions "
            "promotionStartDateFrom and promotionStartDateTo. Use 89 days to avoid "
            "edge cases around 90-day windows."
        ),
    ),
    ReportSamplingPlanItem(
        report_type=rt.COUPON_PERFORMANCE,
        mode="request",
        label="Coupon performance, 89 days",
        purpose="Coupon redemption/performance if available for the seller account.",
        days=89,
        report_options={
            "couponStartDateFrom": "{data_start_time}",
            "couponStartDateTo": "{data_end_time}",
        },
        priority=150,
        notes=(
            "Diagnostic sampling showed this report requires reportOptions "
            "couponStartDateFrom and couponStartDateTo. Use 89 days to avoid edge "
            "cases around 90-day windows."
        ),
    ),
    ReportSamplingPlanItem(
        report_type=rt.FBA_FULFILLED_SHIPMENTS,
        mode="request",
        label="FBA fulfilled shipments, 30 days",
        purpose="Shipment-level sales, promotion discounts, carrier, tracking, fulfillment center.",
        days=30,
        priority=160,
        sensitive=True,
        notes=(
            "Can include buyer/contact/address fields. Excluded unless --include-sensitive is used."
        ),
    ),
)


def get_sampling_plan(*, include_sensitive: bool = False) -> list[ReportSamplingPlanItem]:
    items = sorted(CORE_SAMPLING_PLAN, key=lambda item: item.priority)
    if include_sensitive:
        return items
    return [item for item in items if not item.sensitive]


__all__ = ["CORE_SAMPLING_PLAN", "ReportSamplingPlanItem", "get_sampling_plan"]
