from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from seller_data_pipeline.parsers.amazon.promotion_coupon_parser import (
    COUPON_PERFORMANCE_REPORT_TYPE,
    PROMOTION_PERFORMANCE_REPORT_TYPE,
    CouponAsinRecord,
    CouponPerformanceRecord,
    PromotionIncludedProductRecord,
    PromotionPerformanceRecord,
)

PROMOTION_PERFORMANCE_TARGET_TABLE = "amazon_promotion_performance"
PROMOTION_PRODUCT_TARGET_TABLE = "amazon_promotion_product_performance"
COUPON_PERFORMANCE_TARGET_TABLE = "amazon_coupon_performance"
COUPON_ASIN_TARGET_TABLE = "amazon_coupon_asin"

PROMOTION_PERFORMANCE_EXPECTED_FIELDS: tuple[str, ...] = (
    "reportSpecification.reportType",
    "reportSpecification.reportOptions.promotionStartDateFrom",
    "reportSpecification.reportOptions.promotionStartDateTo",
    "reportSpecification.marketplaceIds[]",
    "promotions[].promotionId",
    "promotions[].marketplaceId",
    "promotions[].merchantId",
    "promotions[].promotionName",
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
)
PROMOTION_PERFORMANCE_REQUIRED_FIELDS: tuple[str, ...] = (
    "reportSpecification.reportType",
    "reportSpecification.marketplaceIds[]",
)

COUPON_PERFORMANCE_EXPECTED_FIELDS: tuple[str, ...] = (
    "reportSpecification.reportType",
    "reportSpecification.reportOptions.couponStartDateFrom",
    "reportSpecification.reportOptions.couponStartDateTo",
    "reportSpecification.marketplaceIds[]",
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
)
COUPON_PERFORMANCE_REQUIRED_FIELDS: tuple[str, ...] = (
    "reportSpecification.reportType",
    "reportSpecification.marketplaceIds[]",
)


@dataclass(frozen=True)
class PromotionCouponTargetTableSpec:
    report_type: str
    target_table: str
    business_key_fields: tuple[str, ...]
    table_columns: tuple[str, ...]
    expected_fields: tuple[str, ...]
    required_fields: tuple[str, ...]


PROMOTION_PERFORMANCE_TARGET_TABLE_SPEC = PromotionCouponTargetTableSpec(
    report_type=PROMOTION_PERFORMANCE_REPORT_TYPE,
    target_table=PROMOTION_PERFORMANCE_TARGET_TABLE,
    business_key_fields=(
        "marketplace_id",
        "source_report_type",
        "promotion_id",
        "merchant_id",
        "start_date_time_raw",
        "end_date_time_raw",
    ),
    table_columns=(
        "marketplace_id",
        "promotion_id",
        "merchant_id",
        "promotion_name",
        "promotion_type",
        "status",
        "glance_views",
        "units_sold",
        "revenue",
        "revenue_currency_code",
        "start_date_time_raw",
        "end_date_time_raw",
        "created_date_time_raw",
        "last_updated_date_time_raw",
        "source_system",
        "source_report_type",
        "source_report_id",
        "source_report_request_id",
        "source_raw_file_id",
        "source_raw_file_path",
        "source_run_id",
        "source_row_hash",
        "raw_data",
        "source_row_index",
        "business_key_hash",
    ),
    expected_fields=PROMOTION_PERFORMANCE_EXPECTED_FIELDS,
    required_fields=PROMOTION_PERFORMANCE_REQUIRED_FIELDS,
)

PROMOTION_PRODUCT_TARGET_TABLE_SPEC = PromotionCouponTargetTableSpec(
    report_type=PROMOTION_PERFORMANCE_REPORT_TYPE,
    target_table=PROMOTION_PRODUCT_TARGET_TABLE,
    business_key_fields=(
        "marketplace_id",
        "source_report_type",
        "promotion_id",
        "merchant_id",
        "asin",
    ),
    table_columns=(
        "marketplace_id",
        "promotion_id",
        "merchant_id",
        "promotion_name",
        "promotion_type",
        "status",
        "asin",
        "product_name",
        "product_glance_views",
        "product_units_sold",
        "product_revenue",
        "product_revenue_currency_code",
        "source_system",
        "source_report_type",
        "source_report_id",
        "source_report_request_id",
        "source_raw_file_id",
        "source_raw_file_path",
        "source_run_id",
        "source_row_hash",
        "raw_data",
        "source_row_index",
        "business_key_hash",
    ),
    expected_fields=PROMOTION_PERFORMANCE_EXPECTED_FIELDS,
    required_fields=PROMOTION_PERFORMANCE_REQUIRED_FIELDS,
)

COUPON_PERFORMANCE_TARGET_TABLE_SPEC = PromotionCouponTargetTableSpec(
    report_type=COUPON_PERFORMANCE_REPORT_TYPE,
    target_table=COUPON_PERFORMANCE_TARGET_TABLE,
    business_key_fields=(
        "marketplace_id",
        "source_report_type",
        "coupon_id",
        "merchant_id",
        "start_date_time_raw",
        "end_date_time_raw",
    ),
    table_columns=(
        "marketplace_id",
        "coupon_id",
        "merchant_id",
        "currency_code",
        "name",
        "website_message",
        "start_date_time_raw",
        "end_date_time_raw",
        "discount_type",
        "discount_amount",
        "total_discount",
        "clips",
        "redemptions",
        "budget",
        "budget_spent",
        "budget_remaining",
        "budget_percentage_used",
        "sales",
        "source_system",
        "source_report_type",
        "source_report_id",
        "source_report_request_id",
        "source_raw_file_id",
        "source_raw_file_path",
        "source_run_id",
        "source_row_hash",
        "raw_data",
        "source_row_index",
        "business_key_hash",
    ),
    expected_fields=COUPON_PERFORMANCE_EXPECTED_FIELDS,
    required_fields=COUPON_PERFORMANCE_REQUIRED_FIELDS,
)

COUPON_ASIN_TARGET_TABLE_SPEC = PromotionCouponTargetTableSpec(
    report_type=COUPON_PERFORMANCE_REPORT_TYPE,
    target_table=COUPON_ASIN_TARGET_TABLE,
    business_key_fields=(
        "marketplace_id",
        "source_report_type",
        "coupon_id",
        "merchant_id",
        "asin",
    ),
    table_columns=(
        "marketplace_id",
        "coupon_id",
        "merchant_id",
        "asin",
        "coupon_name",
        "currency_code",
        "start_date_time_raw",
        "end_date_time_raw",
        "source_system",
        "source_report_type",
        "source_report_id",
        "source_report_request_id",
        "source_raw_file_id",
        "source_raw_file_path",
        "source_run_id",
        "source_row_hash",
        "raw_data",
        "source_row_index",
        "business_key_hash",
    ),
    expected_fields=COUPON_PERFORMANCE_EXPECTED_FIELDS,
    required_fields=COUPON_PERFORMANCE_REQUIRED_FIELDS,
)

PROMOTION_COUPON_TARGET_TABLE_SPECS: tuple[PromotionCouponTargetTableSpec, ...] = (
    PROMOTION_PERFORMANCE_TARGET_TABLE_SPEC,
    PROMOTION_PRODUCT_TARGET_TABLE_SPEC,
    COUPON_PERFORMANCE_TARGET_TABLE_SPEC,
    COUPON_ASIN_TARGET_TABLE_SPEC,
)


def get_promotion_coupon_target_table_spec(
    target_table: str,
) -> PromotionCouponTargetTableSpec | None:
    for spec in PROMOTION_COUPON_TARGET_TABLE_SPECS:
        if spec.target_table == target_table:
            return spec
    return None


def map_promotion_performance_record_to_table_row(
    record: PromotionPerformanceRecord,
    *,
    source_row_index: int,
) -> dict[str, Any]:
    return _prepare_row(
        record.to_dict(),
        source_row_index=source_row_index,
        table_spec=PROMOTION_PERFORMANCE_TARGET_TABLE_SPEC,
    )


def map_promotion_product_record_to_table_row(
    record: PromotionIncludedProductRecord,
    *,
    source_row_index: int,
) -> dict[str, Any]:
    return _prepare_row(
        record.to_dict(),
        source_row_index=source_row_index,
        table_spec=PROMOTION_PRODUCT_TARGET_TABLE_SPEC,
    )


def map_coupon_performance_record_to_table_row(
    record: CouponPerformanceRecord,
    *,
    source_row_index: int,
) -> dict[str, Any]:
    return _prepare_row(
        record.to_dict(),
        source_row_index=source_row_index,
        table_spec=COUPON_PERFORMANCE_TARGET_TABLE_SPEC,
    )


def map_coupon_asin_record_to_table_row(
    record: CouponAsinRecord,
    *,
    source_row_index: int,
) -> dict[str, Any]:
    return _prepare_row(
        record.to_dict(),
        source_row_index=source_row_index,
        table_spec=COUPON_ASIN_TARGET_TABLE_SPEC,
    )


def compute_promotion_coupon_business_key_hash(
    *,
    row: dict[str, Any],
    table_spec: PromotionCouponTargetTableSpec,
) -> str:
    return compute_business_key_hash(
        target_table=table_spec.target_table,
        business_key_fields=table_spec.business_key_fields,
        row=row,
    )


def compute_business_key_hash(
    *,
    target_table: str,
    business_key_fields: tuple[str, ...],
    row: dict[str, Any],
) -> str:
    key_payload = {
        "target_table": target_table,
        "business_key": {field: _json_ready(row.get(field)) for field in business_key_fields},
    }
    canonical = json.dumps(
        key_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_json_dumps(row) + "\n")
    return output_path


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def _prepare_row(
    base_row: dict[str, Any],
    *,
    source_row_index: int,
    table_spec: PromotionCouponTargetTableSpec,
) -> dict[str, Any]:
    row = dict(base_row)
    row["source_report_request_id"] = None
    row["source_raw_file_id"] = None
    row["source_run_id"] = None
    row["source_row_index"] = source_row_index
    row["business_key_hash"] = compute_promotion_coupon_business_key_hash(
        row=row,
        table_spec=table_spec,
    )
    row["raw_data"] = _json_dumps(row.get("raw_data", {}))
    return {column: _json_ready(row.get(column)) for column in table_spec.table_columns}


def _json_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_ready(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_json_ready(child) for child in value]
    if isinstance(value, tuple):
        return [_json_ready(child) for child in value]
    return value


def _json_dumps(value: Any) -> str:
    return json.dumps(_json_ready(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


__all__ = [
    "COUPON_ASIN_TARGET_TABLE",
    "COUPON_ASIN_TARGET_TABLE_SPEC",
    "COUPON_PERFORMANCE_EXPECTED_FIELDS",
    "COUPON_PERFORMANCE_REQUIRED_FIELDS",
    "COUPON_PERFORMANCE_TARGET_TABLE",
    "COUPON_PERFORMANCE_TARGET_TABLE_SPEC",
    "PROMOTION_COUPON_TARGET_TABLE_SPECS",
    "PROMOTION_PERFORMANCE_EXPECTED_FIELDS",
    "PROMOTION_PERFORMANCE_REQUIRED_FIELDS",
    "PROMOTION_PERFORMANCE_TARGET_TABLE",
    "PROMOTION_PERFORMANCE_TARGET_TABLE_SPEC",
    "PROMOTION_PRODUCT_TARGET_TABLE",
    "PROMOTION_PRODUCT_TARGET_TABLE_SPEC",
    "PromotionCouponTargetTableSpec",
    "compute_business_key_hash",
    "compute_promotion_coupon_business_key_hash",
    "get_promotion_coupon_target_table_spec",
    "map_coupon_asin_record_to_table_row",
    "map_coupon_performance_record_to_table_row",
    "map_promotion_performance_record_to_table_row",
    "map_promotion_product_record_to_table_row",
    "read_jsonl",
    "write_jsonl",
]
