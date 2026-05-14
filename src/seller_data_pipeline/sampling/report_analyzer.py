from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from seller_data_pipeline.sampling.raw_report_files import (
    decode_report_content,
    detect_report_delimiter,
)

DEFAULT_SENSITIVE_FIELD_PATTERNS = (
    "sku",
    "asin",
    "listing-id",
    "product-id",
    "item-name",
    "item-description",
    "image-url",
    "title",
    "description",
    "order-id",
    "order id",
    "order-item-id",
    "order item id",
    "rma",
    "tracking",
    "postal",
    "city",
    "state",
    "cpf",
    "reimbursement-id",
    "case-id",
    "email",
    "name",
    "address",
    "phone",
    "message",
)

DATE_FIELD_PATTERN = re.compile(r"(^|[-_ .])date($|[-_ .])|open-date|created|updated", re.I)

LISTING_MAPPED_FIELDS = {
    "listing-id",
    "seller-sku",
    "asin1",
    "product-id",
    "product-id-type",
    "item-name",
    "item-description",
    "price",
    "quantity",
    "open-date",
    "item-is-marketplace",
    "item-condition",
    "pending-quantity",
    "fulfillment-channel",
    "merchant-shipping-group",
    "status",
}

FBA_INVENTORY_MAPPED_FIELDS = {
    "sku",
    "fnsku",
    "asin",
    "product-name",
    "condition",
    "your-price",
    "mfn-listing-exists",
    "mfn-fulfillable-quantity",
    "afn-listing-exists",
    "afn-warehouse-quantity",
    "afn-fulfillable-quantity",
    "afn-unsellable-quantity",
    "afn-reserved-quantity",
    "afn-total-quantity",
    "per-unit-volume",
    "afn-inbound-working-quantity",
    "afn-inbound-shipped-quantity",
    "afn-inbound-receiving-quantity",
    "afn-researching-quantity",
    "afn-reserved-future-supply",
    "afn-future-supply-buyable",
    "store",
}

SALES_AND_TRAFFIC_MAPPED_FIELDS = {
    "reportSpecification.dataEndTime",
    "reportSpecification.dataStartTime",
    "reportSpecification.marketplaceIds[]",
    "reportSpecification.reportOptions.asinGranularity",
    "reportSpecification.reportOptions.dateGranularity",
    "reportSpecification.reportType",
    "salesAndTrafficByAsin[].parentAsin",
    "salesAndTrafficByAsin[].salesByAsin.orderedProductSales.amount",
    "salesAndTrafficByAsin[].salesByAsin.orderedProductSales.currencyCode",
    "salesAndTrafficByAsin[].salesByAsin.orderedProductSalesB2B.amount",
    "salesAndTrafficByAsin[].salesByAsin.orderedProductSalesB2B.currencyCode",
    "salesAndTrafficByAsin[].salesByAsin.totalOrderItems",
    "salesAndTrafficByAsin[].salesByAsin.totalOrderItemsB2B",
    "salesAndTrafficByAsin[].salesByAsin.unitsOrdered",
    "salesAndTrafficByAsin[].salesByAsin.unitsOrderedB2B",
    "salesAndTrafficByAsin[].trafficByAsin.browserPageViews",
    "salesAndTrafficByAsin[].trafficByAsin.browserPageViewsB2B",
    "salesAndTrafficByAsin[].trafficByAsin.browserPageViewsPercentage",
    "salesAndTrafficByAsin[].trafficByAsin.browserPageViewsPercentageB2B",
    "salesAndTrafficByAsin[].trafficByAsin.browserSessionPercentage",
    "salesAndTrafficByAsin[].trafficByAsin.browserSessionPercentageB2B",
    "salesAndTrafficByAsin[].trafficByAsin.browserSessions",
    "salesAndTrafficByAsin[].trafficByAsin.browserSessionsB2B",
    "salesAndTrafficByAsin[].trafficByAsin.buyBoxPercentage",
    "salesAndTrafficByAsin[].trafficByAsin.buyBoxPercentageB2B",
    "salesAndTrafficByAsin[].trafficByAsin.mobileAppPageViews",
    "salesAndTrafficByAsin[].trafficByAsin.mobileAppPageViewsB2B",
    "salesAndTrafficByAsin[].trafficByAsin.mobileAppPageViewsPercentage",
    "salesAndTrafficByAsin[].trafficByAsin.mobileAppPageViewsPercentageB2B",
    "salesAndTrafficByAsin[].trafficByAsin.mobileAppSessionPercentage",
    "salesAndTrafficByAsin[].trafficByAsin.mobileAppSessionPercentageB2B",
    "salesAndTrafficByAsin[].trafficByAsin.mobileAppSessions",
    "salesAndTrafficByAsin[].trafficByAsin.mobileAppSessionsB2B",
    "salesAndTrafficByAsin[].trafficByAsin.pageViews",
    "salesAndTrafficByAsin[].trafficByAsin.pageViewsB2B",
    "salesAndTrafficByAsin[].trafficByAsin.pageViewsPercentage",
    "salesAndTrafficByAsin[].trafficByAsin.pageViewsPercentageB2B",
    "salesAndTrafficByAsin[].trafficByAsin.sessionPercentage",
    "salesAndTrafficByAsin[].trafficByAsin.sessionPercentageB2B",
    "salesAndTrafficByAsin[].trafficByAsin.sessions",
    "salesAndTrafficByAsin[].trafficByAsin.sessionsB2B",
    "salesAndTrafficByAsin[].trafficByAsin.unitSessionPercentage",
    "salesAndTrafficByAsin[].trafficByAsin.unitSessionPercentageB2B",
    "salesAndTrafficByDate[].date",
    "salesAndTrafficByDate[].salesByDate.averageSalesPerOrderItem.amount",
    "salesAndTrafficByDate[].salesByDate.averageSalesPerOrderItem.currencyCode",
    "salesAndTrafficByDate[].salesByDate.averageSalesPerOrderItemB2B.amount",
    "salesAndTrafficByDate[].salesByDate.averageSalesPerOrderItemB2B.currencyCode",
    "salesAndTrafficByDate[].salesByDate.averageSellingPrice.amount",
    "salesAndTrafficByDate[].salesByDate.averageSellingPrice.currencyCode",
    "salesAndTrafficByDate[].salesByDate.averageSellingPriceB2B.amount",
    "salesAndTrafficByDate[].salesByDate.averageSellingPriceB2B.currencyCode",
    "salesAndTrafficByDate[].salesByDate.averageUnitsPerOrderItem",
    "salesAndTrafficByDate[].salesByDate.averageUnitsPerOrderItemB2B",
    "salesAndTrafficByDate[].salesByDate.claimsAmount.amount",
    "salesAndTrafficByDate[].salesByDate.claimsAmount.currencyCode",
    "salesAndTrafficByDate[].salesByDate.claimsGranted",
    "salesAndTrafficByDate[].salesByDate.orderedProductSales.amount",
    "salesAndTrafficByDate[].salesByDate.orderedProductSales.currencyCode",
    "salesAndTrafficByDate[].salesByDate.orderedProductSalesB2B.amount",
    "salesAndTrafficByDate[].salesByDate.orderedProductSalesB2B.currencyCode",
    "salesAndTrafficByDate[].salesByDate.ordersShipped",
    "salesAndTrafficByDate[].salesByDate.refundRate",
    "salesAndTrafficByDate[].salesByDate.shippedProductSales.amount",
    "salesAndTrafficByDate[].salesByDate.shippedProductSales.currencyCode",
    "salesAndTrafficByDate[].salesByDate.totalOrderItems",
    "salesAndTrafficByDate[].salesByDate.totalOrderItemsB2B",
    "salesAndTrafficByDate[].salesByDate.unitsOrdered",
    "salesAndTrafficByDate[].salesByDate.unitsOrderedB2B",
    "salesAndTrafficByDate[].salesByDate.unitsRefunded",
    "salesAndTrafficByDate[].salesByDate.unitsShipped",
    "salesAndTrafficByDate[].trafficByDate.averageOfferCount",
    "salesAndTrafficByDate[].trafficByDate.averageParentItems",
    "salesAndTrafficByDate[].trafficByDate.browserPageViews",
    "salesAndTrafficByDate[].trafficByDate.browserPageViewsB2B",
    "salesAndTrafficByDate[].trafficByDate.browserSessions",
    "salesAndTrafficByDate[].trafficByDate.browserSessionsB2B",
    "salesAndTrafficByDate[].trafficByDate.buyBoxPercentage",
    "salesAndTrafficByDate[].trafficByDate.buyBoxPercentageB2B",
    "salesAndTrafficByDate[].trafficByDate.feedbackReceived",
    "salesAndTrafficByDate[].trafficByDate.mobileAppPageViews",
    "salesAndTrafficByDate[].trafficByDate.mobileAppPageViewsB2B",
    "salesAndTrafficByDate[].trafficByDate.mobileAppSessions",
    "salesAndTrafficByDate[].trafficByDate.mobileAppSessionsB2B",
    "salesAndTrafficByDate[].trafficByDate.negativeFeedbackReceived",
    "salesAndTrafficByDate[].trafficByDate.orderItemSessionPercentage",
    "salesAndTrafficByDate[].trafficByDate.orderItemSessionPercentageB2B",
    "salesAndTrafficByDate[].trafficByDate.pageViews",
    "salesAndTrafficByDate[].trafficByDate.pageViewsB2B",
    "salesAndTrafficByDate[].trafficByDate.receivedNegativeFeedbackRate",
    "salesAndTrafficByDate[].trafficByDate.sessions",
    "salesAndTrafficByDate[].trafficByDate.sessionsB2B",
    "salesAndTrafficByDate[].trafficByDate.unitSessionPercentage",
    "salesAndTrafficByDate[].trafficByDate.unitSessionPercentageB2B",
}


ALL_ORDERS_MAPPED_FIELDS = {
    "amazon-order-id",
    "merchant-order-id",
    "purchase-date",
    "last-updated-date",
    "order-status",
    "fulfillment-channel",
    "sales-channel",
    "order-channel",
    "ship-service-level",
    "product-name",
    "sku",
    "asin",
    "item-status",
    "quantity",
    "currency",
    "item-price",
    "item-tax",
    "shipping-price",
    "shipping-tax",
    "gift-wrap-price",
    "gift-wrap-tax",
    "item-promotion-discount",
    "ship-promotion-discount",
    "ship-city",
    "ship-state",
    "ship-postal-code",
    "ship-country",
    "promotion-ids",
    "cpf",
    "is-business-order",
    "purchase-order-number",
    "price-designation",
    "signature-confirmation-recommended",
}

RETURNS_BY_RETURN_DATE_MAPPED_FIELDS = {
    "Order ID",
    "Order date",
    "Return request date",
    "Return request status",
    "Amazon RMA ID",
    "Merchant RMA ID",
    "Label type",
    "Label cost",
    "Currency code",
    "Return carrier",
    "Tracking ID",
    "Label to be paid by",
    "A-to-Z Claim",
    "Is prime",
    "ASIN",
    "Merchant SKU",
    "Item Name",
    "Return quantity",
    "Return Reason",
    "In policy",
    "Return type",
    "Resolution",
    "Invoice number",
    "Return delivery date",
    "Order Amount",
    "Order quantity",
    "SafeT Action reason",
    "SafeT claim id",
    "SafeT claim state",
    "SafeT claim creation time",
    "SafeT claim reimbursement amount",
    "Refunded Amount",
    "Order Item ID",
}

FBA_REIMBURSEMENTS_MAPPED_FIELDS = {
    "approval-date",
    "reimbursement-id",
    "case-id",
    "amazon-order-id",
    "reason",
    "sku",
    "fnsku",
    "asin",
    "product-name",
    "condition",
    "currency-unit",
    "amount-per-unit",
    "amount-total",
    "quantity-reimbursed-cash",
    "quantity-reimbursed-inventory",
    "quantity-reimbursed-total",
    "original-reimbursement-id",
    "original-reimbursement-type",
}

FBA_ESTIMATED_FEES_MAPPED_FIELDS = {
    "sku",
    "fnsku",
    "asin",
    "amazon-store",
    "product-name",
    "product-group",
    "brand",
    "fulfilled-by",
    "your-price",
    "sales-price",
    "longest-side",
    "median-side",
    "shortest-side",
    "length-and-girth",
    "unit-of-dimension",
    "item-package-weight",
    "unit-of-weight",
    "product-size-tier",
    "currency",
    "estimated-fee-total",
    "estimated-referral-fee-per-unit",
    "estimated-variable-closing-fee",
    "estimated-order-handling-fee-per-order",
    "estimated-pick-pack-fee-per-unit",
    "estimated-weight-handling-fee-per-unit",
    "expected-fulfillment-fee-per-unit",
    "estimated-future-fee (Current Selling on Amazon + Future Fulfillment fees)",
    "estimated-future-order-handling-fee-per-order",
    "estimated-future-pick-pack-fee-per-unit",
    "estimated-future-weight-handling-fee-per-unit",
    "expected-future-fulfillment-fee-per-unit",
}

FBA_INVENTORY_PLANNING_MAPPED_FIELDS = {
    "snapshot-date",
    "sku",
    "fnsku",
    "asin",
    "product-name",
    "condition",
    "available",
    "pending-removal-quantity",
    "inv-age-0-to-90-days",
    "inv-age-91-to-180-days",
    "inv-age-181-to-270-days",
    "inv-age-271-to-365-days",
    "inv-age-366-to-455-days",
    "inv-age-456-plus-days",
    "currency",
    "units-shipped-t7",
    "units-shipped-t30",
    "units-shipped-t60",
    "units-shipped-t90",
    "alert",
    "your-price",
    "sales-price",
    "recommended-action",
    "recommended-sales-price",
    "recommended-sale-duration-days",
    "recommended-removal-quantity",
    "estimated-cost-savings-of-recommended-actions",
    "sell-through",
    "item-volume",
    "volume-unit-measurement",
    "storage-type",
    "storage-volume",
    "marketplace",
    "product-group",
    "sales-rank",
    "days-of-supply",
    "estimated-excess-quantity",
}

LEDGER_SUMMARY_MAPPED_FIELDS = {
    "Date",
    "FNSKU",
    "ASIN",
    "MSKU",
    "Title",
    "Disposition",
    "Starting Warehouse Balance",
    "In Transit Between Warehouses",
    "Receipts",
    "Customer Shipments",
    "Customer Returns",
    "Vendor Returns",
    "Warehouse Transfer In/Out",
    "Found",
    "Lost",
    "Damaged",
    "Disposed",
    "Other Events",
    "Ending Warehouse Balance",
    "Unknown Events",
    "Location",
    "Store",
}

LEDGER_DETAIL_MAPPED_FIELDS = {
    "Date",
    "FNSKU",
    "ASIN",
    "MSKU",
    "Title",
    "Event Type",
    "Reference ID",
    "Quantity",
    "Fulfillment Center",
    "Disposition",
    "Reason",
    "Country",
    "Reconciled Quantity",
    "Unreconciled Quantity",
    "Date and Time",
    "Store",
}

RESERVED_INVENTORY_MAPPED_FIELDS = {
    "sku",
    "fnsku",
    "asin",
    "product-name",
    "reserved_qty",
    "reserved_customerorders",
    "reserved_fc-transfers",
    "reserved_fc-processing",
    "program",
}

RESTOCK_INVENTORY_MAPPED_FIELDS = {
    "Country",
    "Product Name",
    "FNSKU",
    "Merchant SKU",
    "ASIN",
    "Condition",
    "Supplier",
    "Supplier part no.",
    "Currency code",
    "Price",
    "Sales last 30 days",
    "Units Sold Last 30 Days",
    "Total Units",
    "Inbound",
    "Available",
    "FC transfer",
    "FC Processing",
    "Customer Order",
    "Unfulfillable",
    "Working",
    "Shipped",
    "Receiving",
    "Fulfilled by",
    "Total Days of Supply (including units from open shipments)",
    "Days of Supply at Amazon Fulfillment Network",
    "Alert",
    "Recommended replenishment qty",
    "Recommended ship date",
    "Recommended action",
    "Unit storage size",
}

SETTLEMENT_V2_MAPPED_FIELDS = {
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
}

PROMOTION_PERFORMANCE_MAPPED_FIELDS = {
    "reportSpecification.marketplaceIds[]",
    "reportSpecification.reportOptions.promotionStartDateFrom",
    "reportSpecification.reportOptions.promotionStartDateTo",
    "reportSpecification.reportType",
    "promotions[].promotionId",
    "promotions[].promotionName",
    "promotions[].marketplaceId",
    "promotions[].merchantId",
    "promotions[].type",
    "promotions[].status",
    "promotions[].glanceViews",
    "promotions[].unitsSold",
    "promotions[].revenue",
    "promotions[].revenueCurrencyCode",
    "promotions[].startDateTime",
    "promotions[].endDateTime",
    "promotions[].createdDateTime",
    "promotions[].lastUpdatedDateTime",
    "promotions[].includedProducts[].asin",
    "promotions[].includedProducts[].productName",
    "promotions[].includedProducts[].productGlanceViews",
    "promotions[].includedProducts[].productUnitsSold",
    "promotions[].includedProducts[].productRevenue",
    "promotions[].includedProducts[].productRevenueCurrencyCode",
}

COUPON_PERFORMANCE_MAPPED_FIELDS = {
    "reportSpecification.marketplaceIds[]",
    "reportSpecification.reportOptions.couponStartDateFrom",
    "reportSpecification.reportOptions.couponStartDateTo",
    "reportSpecification.reportType",
    "coupons[].couponId",
    "coupons[].merchantId",
    "coupons[].marketplaceId",
    "coupons[].currencyCode",
    "coupons[].name",
    "coupons[].websiteMessage",
    "coupons[].startDateTime",
    "coupons[].endDateTime",
    "coupons[].discountType",
    "coupons[].discountAmount",
    "coupons[].totalDiscount",
    "coupons[].clips",
    "coupons[].redemptions",
    "coupons[].budget",
    "coupons[].budgetSpent",
    "coupons[].budgetRemaining",
    "coupons[].budgetPercentageUsed",
    "coupons[].sales",
    "coupons[].asins[].asin",
}


@dataclass(frozen=True)
class FieldAnalysis:
    position: int
    source_field_name: str
    non_empty_count: int
    empty_count: int
    non_empty_rate: float
    unique_non_empty_count: int
    data_type_suggestion: str
    mapping_status: str
    sample_values: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReportAnalysis:
    report_type: str
    marketplace_id: str | None
    raw_file_path: str
    encoding: str
    delimiter: str | None
    row_count: int
    column_count: int
    fields: list[FieldAnalysis]
    file_format: str = "delimited"
    notes: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_type": self.report_type,
            "marketplace_id": self.marketplace_id,
            "raw_file_path": self.raw_file_path,
            "encoding": self.encoding,
            "delimiter": self.delimiter,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "file_format": self.file_format,
            "notes": self.notes or [],
            "fields": [field.to_dict() for field in self.fields],
        }


def analyze_report_file(
    *,
    raw_file_path: str | Path,
    report_type: str,
    marketplace_id: str | None = None,
    sample_value_limit: int = 5,
    redact_sample_values: bool = True,
) -> ReportAnalysis:
    """Analyze a downloaded Amazon report, auto-detecting JSON vs flat file."""

    path = Path(raw_file_path)
    text, encoding = decode_report_content(path.read_bytes())
    if _looks_like_json(text):
        return analyze_json_report_text(
            text=text,
            raw_file_path=path,
            report_type=report_type,
            marketplace_id=marketplace_id,
            encoding=encoding,
            sample_value_limit=sample_value_limit,
            redact_sample_values=redact_sample_values,
        )
    return analyze_delimited_report_text(
        text=text,
        raw_file_path=path,
        report_type=report_type,
        marketplace_id=marketplace_id,
        encoding=encoding,
        sample_value_limit=sample_value_limit,
        redact_sample_values=redact_sample_values,
    )


def analyze_delimited_report_file(
    *,
    raw_file_path: str | Path,
    report_type: str,
    marketplace_id: str | None = None,
    sample_value_limit: int = 5,
    redact_sample_values: bool = True,
) -> ReportAnalysis:
    """Analyze a local Amazon flat-file report without requiring database tables."""

    path = Path(raw_file_path)
    text, encoding = decode_report_content(path.read_bytes())
    return analyze_delimited_report_text(
        text=text,
        raw_file_path=path,
        report_type=report_type,
        marketplace_id=marketplace_id,
        encoding=encoding,
        sample_value_limit=sample_value_limit,
        redact_sample_values=redact_sample_values,
    )


def analyze_delimited_report_text(
    *,
    text: str,
    raw_file_path: str | Path,
    report_type: str,
    marketplace_id: str | None,
    encoding: str,
    sample_value_limit: int,
    redact_sample_values: bool,
) -> ReportAnalysis:
    path = Path(raw_file_path)
    delimiter = detect_report_delimiter(text)
    if delimiter is None:
        return ReportAnalysis(
            report_type=report_type,
            marketplace_id=marketplace_id,
            raw_file_path=str(path),
            encoding=encoding,
            delimiter=None,
            row_count=0,
            column_count=0,
            fields=[],
            file_format="unknown",
        )

    lines = text.splitlines()
    reader = csv.DictReader(lines, delimiter=delimiter)
    header = list(reader.fieldnames or [])
    stats = {
        field: {
            "non_empty": 0,
            "empty": 0,
            "unique_values": set(),
            "sample_values": [],
        }
        for field in header
    }
    row_count = 0
    for row in reader:
        row_count += 1
        for field in header:
            value = (row.get(field) or "").strip()
            field_stats = stats[field]
            if value:
                field_stats["non_empty"] += 1
                field_stats["unique_values"].add(value)
                sample_values = field_stats["sample_values"]
                if len(sample_values) < sample_value_limit and value not in sample_values:
                    sample_values.append(value)
            else:
                field_stats["empty"] += 1

    fields: list[FieldAnalysis] = []
    for position, field in enumerate(header, start=1):
        field_stats = stats[field]
        sample_values_raw = list(field_stats["sample_values"])
        fields.append(
            FieldAnalysis(
                position=position,
                source_field_name=field,
                non_empty_count=int(field_stats["non_empty"]),
                empty_count=int(field_stats["empty"]),
                non_empty_rate=_safe_rate(int(field_stats["non_empty"]), row_count),
                unique_non_empty_count=len(field_stats["unique_values"]),
                data_type_suggestion=infer_data_type(field, sample_values_raw),
                mapping_status=suggest_mapping_status(field, sample_values_raw),
                sample_values=[
                    redact_sample_value(field, value) if redact_sample_values else value
                    for value in sample_values_raw
                ],
            )
        )

    return ReportAnalysis(
        report_type=report_type,
        marketplace_id=marketplace_id,
        raw_file_path=str(path),
        encoding=encoding,
        delimiter=delimiter,
        row_count=row_count,
        column_count=len(header),
        fields=fields,
        file_format="delimited",
    )


def analyze_json_report_text(
    *,
    text: str,
    raw_file_path: str | Path,
    report_type: str,
    marketplace_id: str | None,
    encoding: str,
    sample_value_limit: int,
    redact_sample_values: bool,
) -> ReportAnalysis:
    """Analyze a JSON Amazon report by flattening observed scalar paths."""

    path = Path(raw_file_path)
    payload = json.loads(text)
    stats: dict[str, dict[str, Any]] = {}
    _collect_json_scalar_stats(
        payload, stats=stats, prefix="", sample_value_limit=sample_value_limit
    )
    fields: list[FieldAnalysis] = []
    for position, field_name in enumerate(sorted(stats), start=1):
        field_stats = stats[field_name]
        sample_values_raw = [str(value) for value in field_stats["sample_values"]]
        fields.append(
            FieldAnalysis(
                position=position,
                source_field_name=field_name,
                non_empty_count=int(field_stats["non_empty"]),
                empty_count=int(field_stats["empty"]),
                non_empty_rate=1.0 if int(field_stats["non_empty"]) else 0.0,
                unique_non_empty_count=len(field_stats["unique_values"]),
                data_type_suggestion=infer_data_type(field_name, sample_values_raw),
                mapping_status=suggest_mapping_status(field_name, sample_values_raw),
                sample_values=[
                    redact_sample_value(field_name, value) if redact_sample_values else value
                    for value in sample_values_raw
                ],
            )
        )

    notes = _json_report_notes(payload)
    return ReportAnalysis(
        report_type=report_type,
        marketplace_id=marketplace_id,
        raw_file_path=str(path),
        encoding=encoding,
        delimiter=None,
        row_count=_json_primary_row_count(payload),
        column_count=len(fields),
        fields=fields,
        file_format="json",
        notes=notes,
    )


def render_report_analysis_markdown(analysis: ReportAnalysis) -> str:
    delimiter_label = "tab" if analysis.delimiter == "\t" else analysis.delimiter or "n/a"
    lines = [
        f"# {analysis.report_type} 字段取样记录",
        "",
        "> 本文件记录真实 Amazon report 样例的字段结构和初步映射建议。",
        (
            "> 原始报告文件可能包含经营数据，不应提交 GitHub；"
            "本文只保留字段统计和脱敏样例。"
        ),
        "",
        "## 1. 样例元数据",
        "",
        "| 项目 | 值 |",
        "|---|---|",
        f"| source_system | `sp_api_reports` |",
        f"| report_type | `{analysis.report_type}` |",
        f"| marketplace_id | `{analysis.marketplace_id or 'unknown'}` |",
        f"| raw_file_path | `{analysis.raw_file_path}` |",
        f"| file_format | `{analysis.file_format}` |",
        f"| encoding | `{analysis.encoding}` |",
        f"| delimiter | `{delimiter_label}` |",
        f"| row_count | `{analysis.row_count}` |",
        f"| field_path_count | `{analysis.column_count}` |",
    ]
    if analysis.notes:
        lines.extend(["", "## 2. 结构备注", ""])
        lines.extend(f"- {note}" for note in analysis.notes)
        field_heading = "## 3. 字段统计"
    else:
        field_heading = "## 2. 字段统计"
    lines.extend(
        [
            "",
            field_heading,
            "",
            (
                "| # | source_field_name | non_empty | empty | non_empty_rate | "
                "unique | type_suggestion | mapping_status | sample_values |"
            ),
            "|---:|---|---:|---:|---:|---:|---|---|---|",
        ]
    )
    for field in analysis.fields:
        sample_values = ", ".join(f"`{_escape_markdown(value)}`" for value in field.sample_values)
        lines.append(
            "| {position} | `{name}` | {non_empty} | {empty} | {rate:.2f} | {unique} | "
            "`{dtype}` | `{status}` | {samples} |".format(
                position=field.position,
                name=field.source_field_name,
                non_empty=field.non_empty_count,
                empty=field.empty_count,
                rate=field.non_empty_rate,
                unique=field.unique_non_empty_count,
                dtype=field.data_type_suggestion,
                status=field.mapping_status,
                samples=sample_values or "-",
            )
        )
    lines.extend(render_report_specific_notes(analysis))
    return "\n".join(lines) + "\n"


def render_report_specific_notes(analysis: ReportAnalysis) -> list[str]:
    report_type = analysis.report_type
    if report_type == "GET_MERCHANT_LISTINGS_ALL_DATA":
        return [
            "",
            "## 3. 初步结论",
            "",
            (
                "1. 本报告适合生成 `amazon_listing_snapshot`，用于维护 SKU / ASIN / "
                "Listing / 价格 / 状态等基础信息。"
            ),
            (
                "2. FBA 商品在本次样例中 `quantity` 和 `pending-quantity` 为空，"
                "因此不应把本报告作为 FBA 可用库存的唯一来源。"
            ),
            (
                "3. 长文本、图片、zshop 旧字段等暂缓进入正式列，"
                "优先保留在 `raw_data` 和 raw file 中。"
            ),
            "",
            "## 4. 建议目标表",
            "",
            "| 目标表 | 设计状态 | 说明 |",
            "|---|---|---|",
            (
                "| `amazon_listing_snapshot` | `sampling` | "
                "已有真实样例，可继续完善 parser 和字段映射，暂不执行 SQL |"
            ),
            (
                "| `amazon_inventory_daily` | `sampling` | "
                "需要使用 FBA inventory 报告确认真实库存口径 |"
            ),
        ]
    if report_type == "GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA":
        return [
            "",
            "## 3. 初步结论",
            "",
            (
                "1. 本报告适合生成 `amazon_inventory_daily`，用于保存 FBA SKU "
                "库存快照。"
            ),
            (
                "2. `afn-fulfillable-quantity` 可作为第一版运营可售库存主口径；"
                "`afn-total-quantity`、`afn-reserved-quantity`、"
                "`afn-unsellable-quantity` 用于解释库存差异。"
            ),
            (
                "3. 本样例的 `mfn-fulfillable-quantity` 与 `store` 为空，"
                "但仍应保留字段，避免未来 MFN 或多店铺场景信息丢失。"
            ),
            (
                "4. 本报告编码在样例中识别为 cp1252，parser 必须继续使用"
                "统一的编码探测逻辑，不要假设所有 Amazon flat file 都是 UTF-8。"
            ),
            "",
            "## 4. 建议目标表",
            "",
            "| 目标表 | 设计状态 | 说明 |",
            "|---|---|---|",
            (
                "| `amazon_inventory_daily` | `sampling` | "
                "已有真实 FBA 库存样例，可先实现 parser 和字段映射，"
                "暂不执行 SQL |"
            ),
            (
                "| `amazon_listing_snapshot` | `sampling` | "
                "与 Listing 报告配合，用于补充 title / status / listing id 等信息 |"
            ),
        ]
    if report_type == "GET_SALES_AND_TRAFFIC_REPORT":
        by_date_len = _array_length_from_notes(analysis.notes, "salesAndTrafficByDate")
        by_asin_len = _array_length_from_notes(analysis.notes, "salesAndTrafficByAsin")
        asin_status = "sampling" if by_asin_len > 0 else "draft"
        asin_note = (
            f"本次样例包含 `salesAndTrafficByAsin` {by_asin_len} 行，"
            "可开始确认 ASIN 维度字段。"
            if by_asin_len > 0
            else "本次样例 `salesAndTrafficByAsin` 为空，ASIN 维度仍需补样例。"
        )
        return [
            "",
            "## 4. 初步结论",
            "",
            (
                "1. 本报告是 JSON 格式，不是 tab-delimited flat file；"
                "字段以 JSON path 方式记录。"
            ),
            (
                f"2. 本次样例包含 `salesAndTrafficByDate` {by_date_len} 行；"
                f"{asin_note}"
            ),
            (
                "3. 日期维度适合生成 `amazon_sales_traffic_daily`，"
                "用于销售额、订单、退款、session、page view、转化率等运营指标。"
            ),
            (
                "4. ASIN 维度适合生成 `amazon_sales_traffic_asin_daily`，"
                "当前样例为 PARENT 粒度，后续可再测试 CHILD 粒度是否需要。"
            ),
            "",
            "## 5. 建议目标表",
            "",
            "| 目标表 | 设计状态 | 说明 |",
            "|---|---|---|",
            (
                "| `amazon_sales_traffic_daily` | `sampling` | "
                "已有日期维度真实样例，可实现 parser 和字段映射，暂不执行 SQL |"
            ),
            (
                f"| `amazon_sales_traffic_asin_daily` | `{asin_status}` | "
                "已有 ASIN 维度样例时，可进入 parser 和字段映射；暂不执行 SQL |"
            ),
        ]
    if report_type == "GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL":
        return [
            "",
            "## 3. 初步结论",
            "",
            (
                "1. 本报告适合生成 `amazon_order_item`，用于订单/行项目维度"
                "收入、数量、状态、履约渠道和促销折扣分析。"
            ),
            (
                "2. 样例中包含 ship-city / ship-state / ship-postal-code 等地址字段，"
                "正式表建议仅保留低敏国家/州/邮编，raw file 仍不得提交 GitHub。"
            ),
            (
                "3. 本报告销售金额是订单口径，最终利润仍应以 settlement/finance"
                "费用口径做对账。"
            ),
            "",
            "## 4. 建议目标表",
            "",
            "| 目标表 | 设计状态 | 说明 |",
            "|---|---|---|",
            "| `amazon_order_item` | `sampling` | 已有 30 天真实订单样例，暂不执行 SQL |",
        ]
    if report_type == "GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE":
        return [
            "",
            "## 3. 初步结论",
            "",
            (
                "1. 本次返回 header-only，说明当前窗口无可用退货行，"
                "但字段结构已经可用于 parser 和表设计。"
            ),
            (
                "2. 本报告适合生成 `amazon_return_request`，用于 RMA、退货原因、"
                "退货状态、Safe-T 和退款金额分析。"
            ),
            "",
            "## 4. 建议目标表",
            "",
            "| 目标表 | 设计状态 | 说明 |",
            "|---|---|---|",
            "| `amazon_return_request` | `sampling` | 已有字段结构，仍需补含数据行样例 |",
        ]
    if report_type == "GET_FBA_REIMBURSEMENTS_DATA":
        return [
            "",
            "## 3. 初步结论",
            "",
            (
                "1. 本报告适合生成 `amazon_fba_reimbursement`，用于赔偿、"
                "赔库存、赔现金和原始 reimbursement id 追踪。"
            ),
            (
                "2. 样例中 `reason` 可作为赔偿分类初始口径，后续再与"
                " settlement 中 reimbursement 事件对账。"
            ),
            "",
            "## 4. 建议目标表",
            "",
            "| 目标表 | 设计状态 | 说明 |",
            "|---|---|---|",
            "| `amazon_fba_reimbursement` | `sampling` | 已有真实样例，暂不执行 SQL |",
        ]
    if report_type == "GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA":
        return [
            "",
            "## 3. 初步结论",
            "",
            (
                "1. 本报告适合生成 `amazon_fba_fee_preview`，用于 SKU/ASIN 维度"
                "预估 referral fee 和 fulfillment fee。"
            ),
            (
                "2. 样例包含 `amazon-store`，同一 SKU 可能出现 US/CA 等站点行，"
                "正式唯一键应包含 store 或 marketplace。"
            ),
            "",
            "## 4. 建议目标表",
            "",
            "| 目标表 | 设计状态 | 说明 |",
            "|---|---|---|",
            "| `amazon_fba_fee_preview` | `sampling` | 已有真实样例，暂不执行 SQL |",
        ]
    if report_type == "GET_FBA_INVENTORY_PLANNING_DATA":
        return [
            "",
            "## 3. 初步结论",
            "",
            (
                "1. 本报告适合生成 `amazon_inventory_planning_daily`，用于库存健康、"
                "库龄、周转、冗余和建议动作。"
            ),
            (
                "2. 字段较多且部分字段在样例为空，第一版正式列应优先保留"
                " available、库龄、units shipped、days of supply、excess quantity。"
            ),
            "",
            "## 4. 建议目标表",
            "",
            "| 目标表 | 设计状态 | 说明 |",
            "|---|---|---|",
            "| `amazon_inventory_planning_daily` | `sampling` | 已有真实样例，暂不执行 SQL |",
        ]
    if report_type == "GET_LEDGER_SUMMARY_VIEW_DATA":
        return [
            "",
            "## 3. 初步结论",
            "",
            (
                "1. 本报告适合生成 `amazon_inventory_ledger_summary_daily`，用于"
                "库存流水汇总、丢失/损坏/找到/退货/发货等 movement 对账。"
            ),
            (
                "2. 当前样例是 COUNTRY + DAILY 粒度；若后续需要仓库维度，可再请求"
                " aggregateByLocation=FC。"
            ),
            "",
            "## 4. 建议目标表",
            "",
            "| 目标表 | 设计状态 | 说明 |",
            "|---|---|---|",
            "| `amazon_inventory_ledger_summary_daily` | `sampling` | 已有真实样例，暂不执行 SQL |",
        ]

    if report_type == "GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2":
        return [
            "",
            "## 3. 初步结论",
            "",
            (
                "1. 本报告是 Amazon 自动生成的结算报告，不能通过 createReport 主动请求；"
                "应先用 getReports 发现可下载报告，再下载 raw file。"
            ),
            (
                "2. Flat File V2 把金额统一收敛到 `amount-type`、"
                "`amount-description`、`amount` 三列，更适合后续做费用分类和利润归集。"
            ),
            (
                "3. 本报告适合生成 `amazon_settlement_transaction`，作为费用、"
                "退款、赔偿、清算、促销等利润口径的核心原始财务事件表。"
            ),
            (
                "4. 本阶段只确认字段结构和 parser，不直接汇总利润；"
                "费用分类字典需要等真实样例后再补充。"
            ),
            "",
            "## 4. 建议目标表",
            "",
            "| 目标表 | 设计状态 | 说明 |",
            "|---|---|---|",
            (
                "| `amazon_settlement_transaction` | `sampling` | "
                "发现并下载真实结算报告后，用于保存明细财务交易行，暂不执行 SQL |"
            ),
            (
                "| `amazon_finance_event` | `draft` | "
                "可作为后续聚合后的统一财务事件表，需等费用分类规则稳定后再确认 |"
            ),
        ]

    if report_type == "GET_PROMOTION_PERFORMANCE_REPORT":
        product_len = _array_length_from_notes(analysis.notes, "promotions")
        return [
            "",
            "## 4. 初步结论",
            "",
            (
                "1. 本报告是 JSON 格式，用于活动效果分析；第一版利润核算仍以 "
                "Settlement V2 的财务扣费口径为准。"
            ),
            (
                f"2. 本次样例包含 `promotions` {product_len} 行；"
                "每个 promotion 下面可能包含多个 `includedProducts`，"
                "因此建议拆成活动主表和活动商品明细表。"
            ),
            (
                "3. `revenue` / `unitsSold` / `glanceViews` 是运营表现口径，"
                "不应直接等同于最终利润或结算金额。"
            ),
            "",
            "## 5. 建议目标表",
            "",
            "| 目标表 | 设计状态 | 说明 |",
            "|---|---|---|",
            (
                "| `amazon_promotion_performance` | `sampling` | "
                "活动主表，记录 Deal/Promotion 的总体表现，暂不执行 SQL |"
            ),
            (
                "| `amazon_promotion_product_performance` | `sampling` | "
                "活动商品明细表，记录 ASIN 维度表现，暂不执行 SQL |"
            ),
        ]

    if report_type == "GET_COUPON_PERFORMANCE_REPORT":
        coupon_len = _array_length_from_notes(analysis.notes, "coupons")
        return [
            "",
            "## 4. 初步结论",
            "",
            (
                "1. 本报告是 JSON 格式，用于 Coupon 活动效果分析；第一版利润核算仍以 "
                "Settlement V2 的 Coupon/促销扣费口径为准。"
            ),
            (
                f"2. 本次样例包含 `coupons` {coupon_len} 行；"
                "每个 coupon 下面可能包含多个 ASIN，"
                "因此建议拆成 Coupon 主表和 Coupon-ASIN 明细表。"
            ),
            (
                "3. `budgetSpent`、`totalDiscount`、`redemptions`、`sales` "
                "适合评估 Coupon 使用效果，但不应直接替代结算中的实际费用。"
            ),
            "",
            "## 5. 建议目标表",
            "",
            "| 目标表 | 设计状态 | 说明 |",
            "|---|---|---|",
            (
                "| `amazon_coupon_performance` | `sampling` | "
                "Coupon 主表，记录预算、领取、兑换、销售等指标，暂不执行 SQL |"
            ),
            (
                "| `amazon_coupon_asin` | `sampling` | "
                "Coupon 关联 ASIN 明细，暂不执行 SQL |"
            ),
        ]

    return [
        "",
        "## 3. 初步结论",
        "",
        "1. 本报告已完成字段统计，但目标 normalized 表仍需人工确认。",
        "2. 原始字段先保留在 raw file 和 `raw_data` 中，避免过早丢失信息。",
        "",
        "## 4. 建议目标表",
        "",
        "| 目标表 | 设计状态 | 说明 |",
        "|---|---|---|",
        "| 待确认 | `sampling` | 需要结合业务用途和后续样例确认 |",
    ]


def _array_length_from_notes(notes: list[str] | None, array_name: str) -> int:
    if not notes:
        return 0
    pattern = re.compile(rf"`{re.escape(array_name)}` array length = (\d+)")
    for note in notes:
        match = pattern.search(note)
        if match:
            return int(match.group(1))
    return 0


def infer_data_type(field_name: str, values: list[str]) -> str:
    non_empty_values = [value.strip() for value in values if value.strip()]
    if not non_empty_values:
        return "string"
    normalized_field_name = field_name.lower()
    if field_name in {"product-id-type", "item-condition"}:
        return "enum_code"
    if "currencycode" in normalized_field_name or normalized_field_name.endswith("currency"):
        return "currency_code"
    if any(token in normalized_field_name for token in ["amount", "price", "rate", "percentage"]):
        if all(_is_decimal(value) for value in non_empty_values):
            return "decimal"
    if "quantity" in normalized_field_name:
        if all(_is_integer(value) for value in non_empty_values):
            return "integer"
    lowered_values = {value.lower() for value in non_empty_values}
    if lowered_values <= {"y", "n", "yes", "no", "true", "false"}:
        return "boolean_flag"
    if all(_is_integer(value) for value in non_empty_values):
        return "integer"
    if all(_is_decimal(value) for value in non_empty_values):
        return "decimal"
    if DATE_FIELD_PATTERN.search(field_name):
        return "datetime_string"
    return "string"


def suggest_mapping_status(field_name: str, values: list[str]) -> str:
    if (
        field_name in LISTING_MAPPED_FIELDS
        or field_name in FBA_INVENTORY_MAPPED_FIELDS
        or field_name in SALES_AND_TRAFFIC_MAPPED_FIELDS
        or field_name in ALL_ORDERS_MAPPED_FIELDS
        or field_name in RETURNS_BY_RETURN_DATE_MAPPED_FIELDS
        or field_name in FBA_REIMBURSEMENTS_MAPPED_FIELDS
        or field_name in FBA_ESTIMATED_FEES_MAPPED_FIELDS
        or field_name in FBA_INVENTORY_PLANNING_MAPPED_FIELDS
        or field_name in LEDGER_SUMMARY_MAPPED_FIELDS
        or field_name in LEDGER_DETAIL_MAPPED_FIELDS
        or field_name in RESERVED_INVENTORY_MAPPED_FIELDS
        or field_name in RESTOCK_INVENTORY_MAPPED_FIELDS
        or field_name in SETTLEMENT_V2_MAPPED_FIELDS
        or field_name in PROMOTION_PERFORMANCE_MAPPED_FIELDS
        or field_name in COUPON_PERFORMANCE_MAPPED_FIELDS
    ):
        return "mapped_candidate"
    if not values:
        return "deferred"
    return "deferred"


def redact_sample_value(field_name: str, value: str) -> str:
    if not value:
        return ""
    normalized_name = field_name.lower()
    if normalized_name in {"product-id-type", "item-condition"}:
        return value[:80] + ("..." if len(value) > 80 else "")
    if any(pattern in normalized_name for pattern in DEFAULT_SENSITIVE_FIELD_PATTERNS):
        return f"<redacted:{len(value)} chars>"
    business_numeric_tokens = (
        "amount",
        "balance",
        "cost",
        "fee",
        "price",
        "quantity",
        "qty",
        "sales",
        "units",
    )
    if any(token in normalized_name for token in business_numeric_tokens) and _is_decimal(
        value.replace("%", "")
    ):
        return "<redacted:numeric>"
    return value[:80] + ("..." if len(value) > 80 else "")


def _collect_json_scalar_stats(
    value: Any,
    *,
    stats: dict[str, dict[str, Any]],
    prefix: str,
    sample_value_limit: int,
) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            _collect_json_scalar_stats(
                child,
                stats=stats,
                prefix=child_prefix,
                sample_value_limit=sample_value_limit,
            )
        return
    if isinstance(value, list):
        if not value:
            _ensure_json_stat(stats, f"{prefix}[]")
            return
        for item in value:
            _collect_json_scalar_stats(
                item,
                stats=stats,
                prefix=f"{prefix}[]",
                sample_value_limit=sample_value_limit,
            )
        return

    field_stats = _ensure_json_stat(stats, prefix)
    value_str = "" if value is None else str(value)
    if value_str:
        field_stats["non_empty"] += 1
        field_stats["unique_values"].add(value_str)
        if (
            len(field_stats["sample_values"]) < sample_value_limit
            and value_str not in field_stats["sample_values"]
        ):
            field_stats["sample_values"].append(value_str)
    else:
        field_stats["empty"] += 1


def _ensure_json_stat(stats: dict[str, dict[str, Any]], field_name: str) -> dict[str, Any]:
    return stats.setdefault(
        field_name,
        {
            "non_empty": 0,
            "empty": 0,
            "unique_values": set(),
            "sample_values": [],
        },
    )


def _json_primary_row_count(payload: Any) -> int:
    if not isinstance(payload, dict):
        return 0
    candidates = [
        len(value)
        for value in payload.values()
        if isinstance(value, list) and not _is_scalar_list(value)
    ]
    return max(candidates) if candidates else 1


def _json_report_notes(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    notes = []
    for key, value in payload.items():
        if isinstance(value, list):
            notes.append(f"`{key}` array length = {len(value)}")
    return notes


def _is_scalar_list(value: list[Any]) -> bool:
    return all(not isinstance(item, (dict, list)) for item in value)


def _looks_like_json(text: str) -> bool:
    stripped = text.lstrip("\ufeff\n\r\t ")
    return stripped.startswith("{") or stripped.startswith("[")


def _safe_rate(non_empty_count: int, row_count: int) -> float:
    if row_count <= 0:
        return 0.0
    return round(non_empty_count / row_count, 4)


def _is_integer(value: str) -> bool:
    try:
        int(value)
    except ValueError:
        return False
    return True


def _is_decimal(value: str) -> bool:
    try:
        Decimal(value)
    except InvalidOperation:
        return False
    return True


def _escape_markdown(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
