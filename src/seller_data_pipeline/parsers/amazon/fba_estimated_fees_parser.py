from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from seller_data_pipeline.parsers.amazon.flat_file_utils import (
    AmazonFlatFileParser,
    compute_source_row_hash,
    empty_to_none,
    parse_decimal,
    serialize_decimals,
)

FBA_ESTIMATED_FEES_REPORT_TYPE = "GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA"

FBA_ESTIMATED_FEES_REQUIRED_FIELDS = {
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
    "currency",
    "estimated-fee-total",
    "estimated-referral-fee-per-unit",
    "expected-fulfillment-fee-per-unit",
}

_DECIMAL_FIELDS = {
    "your_price",
    "sales_price",
    "longest_side",
    "median_side",
    "shortest_side",
    "length_and_girth",
    "item_package_weight",
    "estimated_fee_total",
    "estimated_referral_fee_per_unit",
    "estimated_variable_closing_fee",
    "estimated_order_handling_fee_per_order",
    "estimated_pick_pack_fee_per_unit",
    "estimated_weight_handling_fee_per_unit",
    "expected_fulfillment_fee_per_unit",
    "estimated_future_fee_total",
    "estimated_future_order_handling_fee_per_order",
    "estimated_future_pick_pack_fee_per_unit",
    "estimated_future_weight_handling_fee_per_unit",
    "expected_future_fulfillment_fee_per_unit",
}

_FUTURE_TOTAL_FIELD = "estimated-future-fee (Current Selling on Amazon + Future Fulfillment fees)"


@dataclass(frozen=True)
class FbaEstimatedFeeRecord:
    marketplace_id: str
    seller_sku: str | None
    fnsku: str | None
    asin: str | None
    amazon_store: str | None
    product_name: str | None
    product_group: str | None
    brand: str | None
    fulfilled_by: str | None
    your_price: Decimal | None
    sales_price: Decimal | None
    longest_side: Decimal | None
    median_side: Decimal | None
    shortest_side: Decimal | None
    length_and_girth: Decimal | None
    unit_of_dimension: str | None
    item_package_weight: Decimal | None
    unit_of_weight: str | None
    product_size_tier: str | None
    currency: str | None
    estimated_fee_total: Decimal | None
    estimated_referral_fee_per_unit: Decimal | None
    estimated_variable_closing_fee: Decimal | None
    estimated_order_handling_fee_per_order: Decimal | None
    estimated_pick_pack_fee_per_unit: Decimal | None
    estimated_weight_handling_fee_per_unit: Decimal | None
    expected_fulfillment_fee_per_unit: Decimal | None
    estimated_future_fee_total: Decimal | None
    estimated_future_order_handling_fee_per_order: Decimal | None
    estimated_future_pick_pack_fee_per_unit: Decimal | None
    estimated_future_weight_handling_fee_per_unit: Decimal | None
    expected_future_fulfillment_fee_per_unit: Decimal | None
    source_system: str
    source_report_type: str
    source_report_id: str | None
    source_raw_file_path: str | None
    source_row_hash: str
    raw_data: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return serialize_decimals(payload, _DECIMAL_FIELDS)


class FbaEstimatedFeesParser(AmazonFlatFileParser):
    """Parser for GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA reports."""

    report_type = FBA_ESTIMATED_FEES_REPORT_TYPE
    required_fields = FBA_ESTIMATED_FEES_REQUIRED_FIELDS

    def row_to_record(
        self,
        *,
        row: dict[str, str],
        marketplace_id: str,
        source_report_id: str | None,
        source_raw_file_path: str | None,
    ) -> FbaEstimatedFeeRecord:
        return FbaEstimatedFeeRecord(
            marketplace_id=marketplace_id,
            seller_sku=empty_to_none(row.get("sku")),
            fnsku=empty_to_none(row.get("fnsku")),
            asin=empty_to_none(row.get("asin")),
            amazon_store=empty_to_none(row.get("amazon-store")),
            product_name=empty_to_none(row.get("product-name")),
            product_group=empty_to_none(row.get("product-group")),
            brand=empty_to_none(row.get("brand")),
            fulfilled_by=empty_to_none(row.get("fulfilled-by")),
            your_price=parse_decimal(row.get("your-price")),
            sales_price=parse_decimal(row.get("sales-price")),
            longest_side=parse_decimal(row.get("longest-side")),
            median_side=parse_decimal(row.get("median-side")),
            shortest_side=parse_decimal(row.get("shortest-side")),
            length_and_girth=parse_decimal(row.get("length-and-girth")),
            unit_of_dimension=empty_to_none(row.get("unit-of-dimension")),
            item_package_weight=parse_decimal(row.get("item-package-weight")),
            unit_of_weight=empty_to_none(row.get("unit-of-weight")),
            product_size_tier=empty_to_none(row.get("product-size-tier")),
            currency=empty_to_none(row.get("currency")),
            estimated_fee_total=parse_decimal(row.get("estimated-fee-total")),
            estimated_referral_fee_per_unit=parse_decimal(
                row.get("estimated-referral-fee-per-unit")
            ),
            estimated_variable_closing_fee=parse_decimal(row.get("estimated-variable-closing-fee")),
            estimated_order_handling_fee_per_order=parse_decimal(
                row.get("estimated-order-handling-fee-per-order")
            ),
            estimated_pick_pack_fee_per_unit=parse_decimal(
                row.get("estimated-pick-pack-fee-per-unit")
            ),
            estimated_weight_handling_fee_per_unit=parse_decimal(
                row.get("estimated-weight-handling-fee-per-unit")
            ),
            expected_fulfillment_fee_per_unit=parse_decimal(
                row.get("expected-fulfillment-fee-per-unit")
            ),
            estimated_future_fee_total=parse_decimal(row.get(_FUTURE_TOTAL_FIELD)),
            estimated_future_order_handling_fee_per_order=parse_decimal(
                row.get("estimated-future-order-handling-fee-per-order")
            ),
            estimated_future_pick_pack_fee_per_unit=parse_decimal(
                row.get("estimated-future-pick-pack-fee-per-unit")
            ),
            estimated_future_weight_handling_fee_per_unit=parse_decimal(
                row.get("estimated-future-weight-handling-fee-per-unit")
            ),
            expected_future_fulfillment_fee_per_unit=parse_decimal(
                row.get("expected-future-fulfillment-fee-per-unit")
            ),
            source_system="sp_api_reports",
            source_report_type=self.report_type,
            source_report_id=source_report_id,
            source_raw_file_path=source_raw_file_path,
            source_row_hash=compute_source_row_hash(row),
            raw_data=row,
        )
