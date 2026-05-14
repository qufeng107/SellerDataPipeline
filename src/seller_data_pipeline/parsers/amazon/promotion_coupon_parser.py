from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from seller_data_pipeline.sampling.raw_report_files import decode_report_content

PROMOTION_PERFORMANCE_REPORT_TYPE = "GET_PROMOTION_PERFORMANCE_REPORT"
COUPON_PERFORMANCE_REPORT_TYPE = "GET_COUPON_PERFORMANCE_REPORT"

_DECIMAL_FIELDS = {
    "revenue",
    "product_revenue",
    "discount_amount",
    "total_discount",
    "budget",
    "budget_spent",
    "budget_remaining",
    "budget_percentage_used",
    "sales",
}


@dataclass(frozen=True)
class PromotionPerformanceRecord:
    marketplace_id: str | None
    promotion_id: str | None
    merchant_id: str | None
    promotion_name: str | None
    promotion_type: str | None
    status: str | None
    glance_views: int | None
    units_sold: int | None
    revenue: Decimal | None
    revenue_currency_code: str | None
    start_date_time_raw: str | None
    end_date_time_raw: str | None
    created_date_time_raw: str | None
    last_updated_date_time_raw: str | None
    source_system: str
    source_report_type: str
    source_report_id: str | None
    source_raw_file_path: str | None
    source_row_hash: str
    raw_data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return _serialize_decimals(asdict(self))


@dataclass(frozen=True)
class PromotionIncludedProductRecord:
    marketplace_id: str | None
    promotion_id: str | None
    merchant_id: str | None
    promotion_name: str | None
    promotion_type: str | None
    status: str | None
    asin: str | None
    product_name: str | None
    product_glance_views: int | None
    product_units_sold: int | None
    product_revenue: Decimal | None
    product_revenue_currency_code: str | None
    source_system: str
    source_report_type: str
    source_report_id: str | None
    source_raw_file_path: str | None
    source_row_hash: str
    raw_data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return _serialize_decimals(asdict(self))


@dataclass(frozen=True)
class PromotionPerformanceParseResult:
    report_specification: dict[str, Any]
    promotions: list[PromotionPerformanceRecord]
    included_products: list[PromotionIncludedProductRecord]

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_specification": self.report_specification,
            "promotions": [record.to_dict() for record in self.promotions],
            "included_products": [record.to_dict() for record in self.included_products],
        }


@dataclass(frozen=True)
class CouponPerformanceRecord:
    marketplace_id: str | None
    coupon_id: str | None
    merchant_id: str | None
    currency_code: str | None
    name: str | None
    website_message: str | None
    start_date_time_raw: str | None
    end_date_time_raw: str | None
    discount_type: str | None
    discount_amount: Decimal | None
    total_discount: Decimal | None
    clips: int | None
    redemptions: int | None
    budget: Decimal | None
    budget_spent: Decimal | None
    budget_remaining: Decimal | None
    budget_percentage_used: Decimal | None
    sales: Decimal | None
    source_system: str
    source_report_type: str
    source_report_id: str | None
    source_raw_file_path: str | None
    source_row_hash: str
    raw_data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return _serialize_decimals(asdict(self))


@dataclass(frozen=True)
class CouponAsinRecord:
    marketplace_id: str | None
    coupon_id: str | None
    merchant_id: str | None
    asin: str | None
    coupon_name: str | None
    currency_code: str | None
    start_date_time_raw: str | None
    end_date_time_raw: str | None
    source_system: str
    source_report_type: str
    source_report_id: str | None
    source_raw_file_path: str | None
    source_row_hash: str
    raw_data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CouponPerformanceParseResult:
    report_specification: dict[str, Any]
    coupons: list[CouponPerformanceRecord]
    coupon_asins: list[CouponAsinRecord]

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_specification": self.report_specification,
            "coupons": [record.to_dict() for record in self.coupons],
            "coupon_asins": [record.to_dict() for record in self.coupon_asins],
        }


class PromotionPerformanceParser:
    """Parser for GET_PROMOTION_PERFORMANCE_REPORT JSON reports."""

    report_type = PROMOTION_PERFORMANCE_REPORT_TYPE

    def parse_file(
        self,
        *,
        raw_file_path: str | Path,
        marketplace_id: str | None = None,
        source_report_id: str | None = None,
    ) -> PromotionPerformanceParseResult:
        path = Path(raw_file_path)
        return self.parse_bytes(
            content=path.read_bytes(),
            marketplace_id=marketplace_id,
            source_report_id=source_report_id,
            source_raw_file_path=str(path),
        )

    def parse_bytes(
        self,
        *,
        content: bytes,
        marketplace_id: str | None = None,
        source_report_id: str | None = None,
        source_raw_file_path: str | None = None,
    ) -> PromotionPerformanceParseResult:
        text, _encoding = decode_report_content(content)
        return self.parse_text(
            text=text,
            marketplace_id=marketplace_id,
            source_report_id=source_report_id,
            source_raw_file_path=source_raw_file_path,
        )

    def parse_text(
        self,
        *,
        text: str,
        marketplace_id: str | None = None,
        source_report_id: str | None = None,
        source_raw_file_path: str | None = None,
    ) -> PromotionPerformanceParseResult:
        payload = json.loads(text)
        report_specification = _dict_or_empty(payload.get("reportSpecification"))
        promotions_payload = _list_or_empty(payload.get("promotions"))
        default_marketplace_id = marketplace_id or _first_marketplace_id(report_specification)

        promotions: list[PromotionPerformanceRecord] = []
        included_products: list[PromotionIncludedProductRecord] = []
        for promotion in promotions_payload:
            if not isinstance(promotion, dict):
                continue
            record_marketplace_id = _string_or_none(
                promotion.get("marketplaceId")
            ) or default_marketplace_id
            promotion_id = _string_or_none(promotion.get("promotionId"))
            merchant_id = _string_or_none(promotion.get("merchantId"))
            promotion_name = _string_or_none(promotion.get("promotionName"))
            promotion_type = _string_or_none(promotion.get("type"))
            status = _string_or_none(promotion.get("status"))
            promotions.append(
                PromotionPerformanceRecord(
                    marketplace_id=record_marketplace_id,
                    promotion_id=promotion_id,
                    merchant_id=merchant_id,
                    promotion_name=promotion_name,
                    promotion_type=promotion_type,
                    status=status,
                    glance_views=_parse_int(promotion.get("glanceViews")),
                    units_sold=_parse_int(promotion.get("unitsSold")),
                    revenue=_parse_decimal(promotion.get("revenue")),
                    revenue_currency_code=_string_or_none(
                        promotion.get("revenueCurrencyCode")
                    ),
                    start_date_time_raw=_string_or_none(promotion.get("startDateTime")),
                    end_date_time_raw=_string_or_none(promotion.get("endDateTime")),
                    created_date_time_raw=_string_or_none(
                        promotion.get("createdDateTime")
                    ),
                    last_updated_date_time_raw=_string_or_none(
                        promotion.get("lastUpdatedDateTime")
                    ),
                    source_system="sp_api_reports",
                    source_report_type=self.report_type,
                    source_report_id=source_report_id,
                    source_raw_file_path=source_raw_file_path,
                    source_row_hash=_compute_source_hash(promotion),
                    raw_data=promotion,
                )
            )
            for product in _list_or_empty(promotion.get("includedProducts")):
                if not isinstance(product, dict):
                    continue
                product_raw = {
                    "promotionId": promotion_id,
                    "merchantId": merchant_id,
                    "promotionName": promotion_name,
                    "type": promotion_type,
                    "status": status,
                    **product,
                }
                included_products.append(
                    PromotionIncludedProductRecord(
                        marketplace_id=record_marketplace_id,
                        promotion_id=promotion_id,
                        merchant_id=merchant_id,
                        promotion_name=promotion_name,
                        promotion_type=promotion_type,
                        status=status,
                        asin=_string_or_none(product.get("asin")),
                        product_name=_string_or_none(product.get("productName")),
                        product_glance_views=_parse_int(
                            product.get("productGlanceViews")
                        ),
                        product_units_sold=_parse_int(product.get("productUnitsSold")),
                        product_revenue=_parse_decimal(product.get("productRevenue")),
                        product_revenue_currency_code=_string_or_none(
                            product.get("productRevenueCurrencyCode")
                        ),
                        source_system="sp_api_reports",
                        source_report_type=self.report_type,
                        source_report_id=source_report_id,
                        source_raw_file_path=source_raw_file_path,
                        source_row_hash=_compute_source_hash(product_raw),
                        raw_data=product_raw,
                    )
                )

        return PromotionPerformanceParseResult(
            report_specification=report_specification,
            promotions=promotions,
            included_products=included_products,
        )

    def parse(self, content: str) -> list[dict[str, Any]]:
        result = self.parse_text(text=content)
        return [record.to_dict() for record in result.promotions]


class CouponPerformanceParser:
    """Parser for GET_COUPON_PERFORMANCE_REPORT JSON reports."""

    report_type = COUPON_PERFORMANCE_REPORT_TYPE

    def parse_file(
        self,
        *,
        raw_file_path: str | Path,
        marketplace_id: str | None = None,
        source_report_id: str | None = None,
    ) -> CouponPerformanceParseResult:
        path = Path(raw_file_path)
        return self.parse_bytes(
            content=path.read_bytes(),
            marketplace_id=marketplace_id,
            source_report_id=source_report_id,
            source_raw_file_path=str(path),
        )

    def parse_bytes(
        self,
        *,
        content: bytes,
        marketplace_id: str | None = None,
        source_report_id: str | None = None,
        source_raw_file_path: str | None = None,
    ) -> CouponPerformanceParseResult:
        text, _encoding = decode_report_content(content)
        return self.parse_text(
            text=text,
            marketplace_id=marketplace_id,
            source_report_id=source_report_id,
            source_raw_file_path=source_raw_file_path,
        )

    def parse_text(
        self,
        *,
        text: str,
        marketplace_id: str | None = None,
        source_report_id: str | None = None,
        source_raw_file_path: str | None = None,
    ) -> CouponPerformanceParseResult:
        payload = json.loads(text)
        report_specification = _dict_or_empty(payload.get("reportSpecification"))
        coupons_payload = _list_or_empty(payload.get("coupons"))
        default_marketplace_id = marketplace_id or _first_marketplace_id(report_specification)

        coupons: list[CouponPerformanceRecord] = []
        coupon_asins: list[CouponAsinRecord] = []
        for coupon in coupons_payload:
            if not isinstance(coupon, dict):
                continue
            record_marketplace_id = _string_or_none(
                coupon.get("marketplaceId")
            ) or default_marketplace_id
            coupon_id = _string_or_none(coupon.get("couponId"))
            merchant_id = _string_or_none(coupon.get("merchantId"))
            coupon_name = _string_or_none(coupon.get("name"))
            currency_code = _string_or_none(coupon.get("currencyCode"))
            start_date_time_raw = _string_or_none(coupon.get("startDateTime"))
            end_date_time_raw = _string_or_none(coupon.get("endDateTime"))
            coupons.append(
                CouponPerformanceRecord(
                    marketplace_id=record_marketplace_id,
                    coupon_id=coupon_id,
                    merchant_id=merchant_id,
                    currency_code=currency_code,
                    name=coupon_name,
                    website_message=_string_or_none(coupon.get("websiteMessage")),
                    start_date_time_raw=start_date_time_raw,
                    end_date_time_raw=end_date_time_raw,
                    discount_type=_string_or_none(coupon.get("discountType")),
                    discount_amount=_parse_decimal(coupon.get("discountAmount")),
                    total_discount=_parse_decimal(coupon.get("totalDiscount")),
                    clips=_parse_int(coupon.get("clips")),
                    redemptions=_parse_int(coupon.get("redemptions")),
                    budget=_parse_decimal(coupon.get("budget")),
                    budget_spent=_parse_decimal(coupon.get("budgetSpent")),
                    budget_remaining=_parse_decimal(coupon.get("budgetRemaining")),
                    budget_percentage_used=_parse_decimal(
                        coupon.get("budgetPercentageUsed")
                    ),
                    sales=_parse_decimal(coupon.get("sales")),
                    source_system="sp_api_reports",
                    source_report_type=self.report_type,
                    source_report_id=source_report_id,
                    source_raw_file_path=source_raw_file_path,
                    source_row_hash=_compute_source_hash(coupon),
                    raw_data=coupon,
                )
            )
            for asin_item in _list_or_empty(coupon.get("asins")):
                if not isinstance(asin_item, dict):
                    continue
                asin_raw = {
                    "couponId": coupon_id,
                    "merchantId": merchant_id,
                    "name": coupon_name,
                    "currencyCode": currency_code,
                    "startDateTime": start_date_time_raw,
                    "endDateTime": end_date_time_raw,
                    **asin_item,
                }
                coupon_asins.append(
                    CouponAsinRecord(
                        marketplace_id=record_marketplace_id,
                        coupon_id=coupon_id,
                        merchant_id=merchant_id,
                        asin=_string_or_none(asin_item.get("asin")),
                        coupon_name=coupon_name,
                        currency_code=currency_code,
                        start_date_time_raw=start_date_time_raw,
                        end_date_time_raw=end_date_time_raw,
                        source_system="sp_api_reports",
                        source_report_type=self.report_type,
                        source_report_id=source_report_id,
                        source_raw_file_path=source_raw_file_path,
                        source_row_hash=_compute_source_hash(asin_raw),
                        raw_data=asin_raw,
                    )
                )

        return CouponPerformanceParseResult(
            report_specification=report_specification,
            coupons=coupons,
            coupon_asins=coupon_asins,
        )

    def parse(self, content: str) -> list[dict[str, Any]]:
        result = self.parse_text(text=content)
        return [record.to_dict() for record in result.coupons]


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _first_marketplace_id(report_specification: dict[str, Any]) -> str | None:
    marketplace_ids = report_specification.get("marketplaceIds")
    if isinstance(marketplace_ids, list) and marketplace_ids:
        return _string_or_none(marketplace_ids[0])
    return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(Decimal(str(value)))


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal value: {value!r}") from exc


def _compute_source_hash(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _serialize_decimals(payload: dict[str, Any]) -> dict[str, Any]:
    for key in _DECIMAL_FIELDS:
        if isinstance(payload.get(key), Decimal):
            payload[key] = str(payload[key])
    return payload
