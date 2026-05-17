from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from seller_data_pipeline.sampling.raw_report_files import decode_report_content

SALES_AND_TRAFFIC_REPORT_TYPE = "GET_SALES_AND_TRAFFIC_REPORT"


@dataclass(frozen=True)
class SalesAndTrafficDateRecord:
    marketplace_id: str
    report_date: str
    date_granularity: str | None
    asin_granularity: str | None
    ordered_product_sales_amount: Decimal | None
    ordered_product_sales_currency: str | None
    ordered_product_sales_b2b_amount: Decimal | None
    ordered_product_sales_b2b_currency: str | None
    average_sales_per_order_item_currency: str | None
    average_sales_per_order_item_b2b_amount: Decimal | None
    average_sales_per_order_item_b2b_currency: str | None
    average_units_per_order_item_b2b: Decimal | None
    average_selling_price_currency: str | None
    average_selling_price_b2b_amount: Decimal | None
    average_selling_price_b2b_currency: str | None
    claims_amount_currency: str | None
    shipped_product_sales_currency: str | None
    units_ordered: int | None
    units_ordered_b2b: int | None
    total_order_items: int | None
    total_order_items_b2b: int | None
    average_sales_per_order_item_amount: Decimal | None
    average_units_per_order_item: Decimal | None
    average_selling_price_amount: Decimal | None
    units_refunded: int | None
    refund_rate: Decimal | None
    claims_granted: int | None
    claims_amount: Decimal | None
    shipped_product_sales_amount: Decimal | None
    units_shipped: int | None
    orders_shipped: int | None
    browser_page_views: int | None
    mobile_app_page_views: int | None
    page_views: int | None
    browser_sessions: int | None
    mobile_app_sessions: int | None
    sessions: int | None
    buy_box_percentage: Decimal | None
    order_item_session_percentage: Decimal | None
    unit_session_percentage: Decimal | None
    average_offer_count: Decimal | None
    average_parent_items: Decimal | None
    feedback_received: int | None
    negative_feedback_received: int | None
    received_negative_feedback_rate: Decimal | None
    source_system: str
    source_report_type: str
    source_report_id: str | None
    source_raw_file_path: str | None
    source_row_hash: str
    raw_data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key, value in list(payload.items()):
            if isinstance(value, Decimal):
                payload[key] = str(value)
        return payload


@dataclass(frozen=True)
class SalesAndTrafficAsinRecord:
    marketplace_id: str
    report_start_date: str | None
    report_end_date: str | None
    parent_asin: str | None
    child_asin: str | None
    date_granularity: str | None
    asin_granularity: str | None
    ordered_product_sales_amount: Decimal | None
    ordered_product_sales_currency: str | None
    ordered_product_sales_b2b_amount: Decimal | None
    ordered_product_sales_b2b_currency: str | None
    units_ordered: int | None
    units_ordered_b2b: int | None
    total_order_items: int | None
    total_order_items_b2b: int | None
    browser_page_views: int | None
    browser_page_views_b2b: int | None
    browser_page_views_percentage: Decimal | None
    browser_page_views_percentage_b2b: Decimal | None
    mobile_app_page_views: int | None
    mobile_app_page_views_b2b: int | None
    mobile_app_page_views_percentage: Decimal | None
    mobile_app_page_views_percentage_b2b: Decimal | None
    page_views: int | None
    page_views_b2b: int | None
    page_views_percentage: Decimal | None
    page_views_percentage_b2b: Decimal | None
    browser_sessions: int | None
    browser_sessions_b2b: int | None
    browser_session_percentage: Decimal | None
    browser_session_percentage_b2b: Decimal | None
    mobile_app_sessions: int | None
    mobile_app_sessions_b2b: int | None
    mobile_app_session_percentage: Decimal | None
    mobile_app_session_percentage_b2b: Decimal | None
    sessions: int | None
    sessions_b2b: int | None
    session_percentage: Decimal | None
    session_percentage_b2b: Decimal | None
    buy_box_percentage: Decimal | None
    buy_box_percentage_b2b: Decimal | None
    unit_session_percentage: Decimal | None
    unit_session_percentage_b2b: Decimal | None
    source_system: str
    source_report_type: str
    source_report_id: str | None
    source_raw_file_path: str | None
    source_row_hash: str
    raw_data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key, value in list(payload.items()):
            if isinstance(value, Decimal):
                payload[key] = str(value)
        return payload


@dataclass(frozen=True)
class SalesAndTrafficParseResult:
    report_specification: dict[str, Any]
    by_date: list[SalesAndTrafficDateRecord]
    by_asin: list[SalesAndTrafficAsinRecord]

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_specification": self.report_specification,
            "by_date": [record.to_dict() for record in self.by_date],
            "by_asin": [record.to_dict() for record in self.by_asin],
        }


class SalesReportParser:
    """Parser for SP-API GET_SALES_AND_TRAFFIC_REPORT JSON reports."""

    def parse_file(
        self,
        *,
        raw_file_path: str | Path,
        marketplace_id: str | None = None,
        source_report_id: str | None = None,
    ) -> SalesAndTrafficParseResult:
        path = Path(raw_file_path)
        text, _encoding = decode_report_content(path.read_bytes())
        return self.parse_text(
            text=text,
            marketplace_id=marketplace_id,
            source_report_id=source_report_id,
            source_raw_file_path=str(path),
        )

    def parse(self, content: str) -> list[dict[str, Any]]:
        """Backward-compatible simple parser entrypoint returning date records as dicts."""

        result = self.parse_text(text=content)
        return [record.to_dict() for record in result.by_date]

    def parse_text(
        self,
        *,
        text: str,
        marketplace_id: str | None = None,
        source_report_id: str | None = None,
        source_raw_file_path: str | None = None,
    ) -> SalesAndTrafficParseResult:
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("Sales and traffic report JSON must be an object")

        specification = _as_dict(payload.get("reportSpecification"))
        report_type = specification.get("reportType")
        if report_type and report_type != SALES_AND_TRAFFIC_REPORT_TYPE:
            raise ValueError(f"Unexpected sales and traffic report type: {report_type!r}")

        marketplaces = specification.get("marketplaceIds")
        effective_marketplace_id = marketplace_id or _first_string(marketplaces) or "UNKNOWN"
        report_options = _as_dict(specification.get("reportOptions"))
        date_granularity = _empty_to_none(report_options.get("dateGranularity"))
        asin_granularity = _empty_to_none(report_options.get("asinGranularity"))
        data_start_time = _empty_to_none(specification.get("dataStartTime"))
        data_end_time = _empty_to_none(specification.get("dataEndTime"))

        by_date = [
            self._parse_by_date_row(
                row=_as_dict(row),
                marketplace_id=effective_marketplace_id,
                date_granularity=date_granularity,
                asin_granularity=asin_granularity,
                source_report_id=source_report_id,
                source_raw_file_path=source_raw_file_path,
            )
            for row in _as_list(payload.get("salesAndTrafficByDate"))
        ]
        by_asin = [
            self._parse_by_asin_row(
                row=_as_dict(row),
                marketplace_id=effective_marketplace_id,
                report_start_date=data_start_time,
                report_end_date=data_end_time,
                date_granularity=date_granularity,
                asin_granularity=asin_granularity,
                source_report_id=source_report_id,
                source_raw_file_path=source_raw_file_path,
            )
            for row in _as_list(payload.get("salesAndTrafficByAsin"))
        ]

        return SalesAndTrafficParseResult(
            report_specification=specification,
            by_date=by_date,
            by_asin=by_asin,
        )

    def _parse_by_date_row(
        self,
        *,
        row: dict[str, Any],
        marketplace_id: str,
        date_granularity: str | None,
        asin_granularity: str | None,
        source_report_id: str | None,
        source_raw_file_path: str | None,
    ) -> SalesAndTrafficDateRecord:
        sales = _as_dict(row.get("salesByDate"))
        traffic = _as_dict(row.get("trafficByDate"))
        ordered_product_sales = _parse_money(sales.get("orderedProductSales"))
        ordered_product_sales_b2b = _parse_money(sales.get("orderedProductSalesB2B"))
        average_sales_per_order_item = _parse_money(sales.get("averageSalesPerOrderItem"))
        average_sales_per_order_item_b2b = _parse_money(sales.get("averageSalesPerOrderItemB2B"))
        average_selling_price = _parse_money(sales.get("averageSellingPrice"))
        average_selling_price_b2b = _parse_money(sales.get("averageSellingPriceB2B"))
        claims_amount = _parse_money(sales.get("claimsAmount"))
        shipped_product_sales = _parse_money(sales.get("shippedProductSales"))

        return SalesAndTrafficDateRecord(
            marketplace_id=marketplace_id,
            report_date=str(row.get("date") or ""),
            date_granularity=date_granularity,
            asin_granularity=asin_granularity,
            ordered_product_sales_amount=ordered_product_sales[0],
            ordered_product_sales_currency=ordered_product_sales[1],
            ordered_product_sales_b2b_amount=ordered_product_sales_b2b[0],
            ordered_product_sales_b2b_currency=ordered_product_sales_b2b[1],
            average_sales_per_order_item_currency=average_sales_per_order_item[1],
            average_sales_per_order_item_b2b_amount=average_sales_per_order_item_b2b[0],
            average_sales_per_order_item_b2b_currency=average_sales_per_order_item_b2b[1],
            average_units_per_order_item_b2b=_parse_decimal(
                sales.get("averageUnitsPerOrderItemB2B")
            ),
            average_selling_price_currency=average_selling_price[1],
            average_selling_price_b2b_amount=average_selling_price_b2b[0],
            average_selling_price_b2b_currency=average_selling_price_b2b[1],
            claims_amount_currency=claims_amount[1],
            shipped_product_sales_currency=shipped_product_sales[1],
            units_ordered=_parse_int(sales.get("unitsOrdered")),
            units_ordered_b2b=_parse_int(sales.get("unitsOrderedB2B")),
            total_order_items=_parse_int(sales.get("totalOrderItems")),
            total_order_items_b2b=_parse_int(sales.get("totalOrderItemsB2B")),
            average_sales_per_order_item_amount=average_sales_per_order_item[0],
            average_units_per_order_item=_parse_decimal(sales.get("averageUnitsPerOrderItem")),
            average_selling_price_amount=average_selling_price[0],
            units_refunded=_parse_int(sales.get("unitsRefunded")),
            refund_rate=_parse_decimal(sales.get("refundRate")),
            claims_granted=_parse_int(sales.get("claimsGranted")),
            claims_amount=claims_amount[0],
            shipped_product_sales_amount=shipped_product_sales[0],
            units_shipped=_parse_int(sales.get("unitsShipped")),
            orders_shipped=_parse_int(sales.get("ordersShipped")),
            browser_page_views=_parse_int(traffic.get("browserPageViews")),
            mobile_app_page_views=_parse_int(traffic.get("mobileAppPageViews")),
            page_views=_parse_int(traffic.get("pageViews")),
            browser_sessions=_parse_int(traffic.get("browserSessions")),
            mobile_app_sessions=_parse_int(traffic.get("mobileAppSessions")),
            sessions=_parse_int(traffic.get("sessions")),
            buy_box_percentage=_parse_decimal(traffic.get("buyBoxPercentage")),
            order_item_session_percentage=_parse_decimal(traffic.get("orderItemSessionPercentage")),
            unit_session_percentage=_parse_decimal(traffic.get("unitSessionPercentage")),
            average_offer_count=_parse_decimal(traffic.get("averageOfferCount")),
            average_parent_items=_parse_decimal(traffic.get("averageParentItems")),
            feedback_received=_parse_int(traffic.get("feedbackReceived")),
            negative_feedback_received=_parse_int(traffic.get("negativeFeedbackReceived")),
            received_negative_feedback_rate=_parse_decimal(
                traffic.get("receivedNegativeFeedbackRate")
            ),
            source_system="sp_api_reports",
            source_report_type=SALES_AND_TRAFFIC_REPORT_TYPE,
            source_report_id=source_report_id,
            source_raw_file_path=source_raw_file_path,
            source_row_hash=compute_source_row_hash(row),
            raw_data=row,
        )

    def _parse_by_asin_row(
        self,
        *,
        row: dict[str, Any],
        marketplace_id: str,
        report_start_date: str | None,
        report_end_date: str | None,
        date_granularity: str | None,
        asin_granularity: str | None,
        source_report_id: str | None,
        source_raw_file_path: str | None,
    ) -> SalesAndTrafficAsinRecord:
        sales = _as_dict(row.get("salesByAsin"))
        traffic = _as_dict(row.get("trafficByAsin"))
        ordered_product_sales = _parse_money(sales.get("orderedProductSales"))
        ordered_product_sales_b2b = _parse_money(sales.get("orderedProductSalesB2B"))

        return SalesAndTrafficAsinRecord(
            marketplace_id=marketplace_id,
            report_start_date=report_start_date,
            report_end_date=report_end_date,
            parent_asin=_empty_to_none(row.get("parentAsin")),
            child_asin=_empty_to_none(row.get("childAsin")),
            date_granularity=date_granularity,
            asin_granularity=asin_granularity,
            ordered_product_sales_amount=ordered_product_sales[0],
            ordered_product_sales_currency=ordered_product_sales[1],
            ordered_product_sales_b2b_amount=ordered_product_sales_b2b[0],
            ordered_product_sales_b2b_currency=ordered_product_sales_b2b[1],
            units_ordered=_parse_int(sales.get("unitsOrdered")),
            units_ordered_b2b=_parse_int(sales.get("unitsOrderedB2B")),
            total_order_items=_parse_int(sales.get("totalOrderItems")),
            total_order_items_b2b=_parse_int(sales.get("totalOrderItemsB2B")),
            browser_page_views=_parse_int(traffic.get("browserPageViews")),
            browser_page_views_b2b=_parse_int(traffic.get("browserPageViewsB2B")),
            browser_page_views_percentage=_parse_decimal(traffic.get("browserPageViewsPercentage")),
            browser_page_views_percentage_b2b=_parse_decimal(
                traffic.get("browserPageViewsPercentageB2B")
            ),
            mobile_app_page_views=_parse_int(traffic.get("mobileAppPageViews")),
            mobile_app_page_views_b2b=_parse_int(traffic.get("mobileAppPageViewsB2B")),
            mobile_app_page_views_percentage=_parse_decimal(
                traffic.get("mobileAppPageViewsPercentage")
            ),
            mobile_app_page_views_percentage_b2b=_parse_decimal(
                traffic.get("mobileAppPageViewsPercentageB2B")
            ),
            page_views=_parse_int(traffic.get("pageViews")),
            page_views_b2b=_parse_int(traffic.get("pageViewsB2B")),
            page_views_percentage=_parse_decimal(traffic.get("pageViewsPercentage")),
            page_views_percentage_b2b=_parse_decimal(traffic.get("pageViewsPercentageB2B")),
            browser_sessions=_parse_int(traffic.get("browserSessions")),
            browser_sessions_b2b=_parse_int(traffic.get("browserSessionsB2B")),
            browser_session_percentage=_parse_decimal(traffic.get("browserSessionPercentage")),
            browser_session_percentage_b2b=_parse_decimal(
                traffic.get("browserSessionPercentageB2B")
            ),
            mobile_app_sessions=_parse_int(traffic.get("mobileAppSessions")),
            mobile_app_sessions_b2b=_parse_int(traffic.get("mobileAppSessionsB2B")),
            mobile_app_session_percentage=_parse_decimal(traffic.get("mobileAppSessionPercentage")),
            mobile_app_session_percentage_b2b=_parse_decimal(
                traffic.get("mobileAppSessionPercentageB2B")
            ),
            sessions=_parse_int(traffic.get("sessions")),
            sessions_b2b=_parse_int(traffic.get("sessionsB2B")),
            session_percentage=_parse_decimal(traffic.get("sessionPercentage")),
            session_percentage_b2b=_parse_decimal(traffic.get("sessionPercentageB2B")),
            buy_box_percentage=_parse_decimal(traffic.get("buyBoxPercentage")),
            buy_box_percentage_b2b=_parse_decimal(traffic.get("buyBoxPercentageB2B")),
            unit_session_percentage=_parse_decimal(traffic.get("unitSessionPercentage")),
            unit_session_percentage_b2b=_parse_decimal(traffic.get("unitSessionPercentageB2B")),
            source_system="sp_api_reports",
            source_report_type=SALES_AND_TRAFFIC_REPORT_TYPE,
            source_report_id=source_report_id,
            source_raw_file_path=source_raw_file_path,
            source_row_hash=compute_source_row_hash(row),
            raw_data=row,
        )


def compute_source_row_hash(row: dict[str, Any]) -> str:
    canonical = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _first_string(value: Any) -> str | None:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item:
                return item
    return None


def _empty_to_none(value: Any) -> str | None:
    if value is None:
        return None
    value_str = str(value).strip()
    return value_str or None


def _parse_money(value: Any) -> tuple[Decimal | None, str | None]:
    value_obj = _as_dict(value)
    return _parse_decimal(value_obj.get("amount")), _empty_to_none(value_obj.get("currencyCode"))


def _parse_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal value: {value!r}") from exc
