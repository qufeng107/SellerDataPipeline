from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from seller_data_pipeline.parsers.amazon.flat_file_utils import (
    AmazonFlatFileParser,
    compute_source_row_hash,
    empty_to_none,
    parse_bool,
    parse_decimal,
    parse_int,
    serialize_decimals,
)

ALL_ORDERS_REPORT_TYPE = "GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL"

ALL_ORDERS_REQUIRED_FIELDS = {
    "amazon-order-id",
    "purchase-date",
    "last-updated-date",
    "order-status",
    "fulfillment-channel",
    "sales-channel",
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
    "item-promotion-discount",
    "ship-promotion-discount",
    "ship-country",
    "promotion-ids",
    "is-business-order",
}

_DECIMAL_FIELDS = {
    "item_price",
    "item_tax",
    "shipping_price",
    "shipping_tax",
    "gift_wrap_price",
    "gift_wrap_tax",
    "item_promotion_discount",
    "ship_promotion_discount",
}


@dataclass(frozen=True)
class AllOrdersItemRecord:
    marketplace_id: str
    amazon_order_id: str | None
    merchant_order_id: str | None
    purchase_date_raw: str | None
    last_updated_date_raw: str | None
    order_status: str | None
    fulfillment_channel: str | None
    sales_channel: str | None
    order_channel: str | None
    ship_service_level: str | None
    product_name: str | None
    seller_sku: str | None
    asin: str | None
    item_status: str | None
    quantity: int | None
    currency: str | None
    item_price: Decimal | None
    item_tax: Decimal | None
    shipping_price: Decimal | None
    shipping_tax: Decimal | None
    gift_wrap_price: Decimal | None
    gift_wrap_tax: Decimal | None
    item_promotion_discount: Decimal | None
    ship_promotion_discount: Decimal | None
    ship_city: str | None
    ship_state: str | None
    ship_postal_code: str | None
    ship_country: str | None
    promotion_ids: str | None
    is_business_order: bool | None
    purchase_order_number: str | None
    price_designation: str | None
    signature_confirmation_recommended: bool | None
    source_system: str
    source_report_type: str
    source_report_id: str | None
    source_raw_file_path: str | None
    source_row_hash: str
    raw_data: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return serialize_decimals(payload, _DECIMAL_FIELDS)


class AllOrdersReportParser(AmazonFlatFileParser):
    """Parser for GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL."""

    report_type = ALL_ORDERS_REPORT_TYPE
    required_fields = ALL_ORDERS_REQUIRED_FIELDS

    def row_to_record(
        self,
        *,
        row: dict[str, str],
        marketplace_id: str,
        source_report_id: str | None,
        source_raw_file_path: str | None,
    ) -> AllOrdersItemRecord:
        return AllOrdersItemRecord(
            marketplace_id=marketplace_id,
            amazon_order_id=empty_to_none(row.get("amazon-order-id")),
            merchant_order_id=empty_to_none(row.get("merchant-order-id")),
            purchase_date_raw=empty_to_none(row.get("purchase-date")),
            last_updated_date_raw=empty_to_none(row.get("last-updated-date")),
            order_status=empty_to_none(row.get("order-status")),
            fulfillment_channel=empty_to_none(row.get("fulfillment-channel")),
            sales_channel=empty_to_none(row.get("sales-channel")),
            order_channel=empty_to_none(row.get("order-channel")),
            ship_service_level=empty_to_none(row.get("ship-service-level")),
            product_name=empty_to_none(row.get("product-name")),
            seller_sku=empty_to_none(row.get("sku")),
            asin=empty_to_none(row.get("asin")),
            item_status=empty_to_none(row.get("item-status")),
            quantity=parse_int(row.get("quantity")),
            currency=empty_to_none(row.get("currency")),
            item_price=parse_decimal(row.get("item-price")),
            item_tax=parse_decimal(row.get("item-tax")),
            shipping_price=parse_decimal(row.get("shipping-price")),
            shipping_tax=parse_decimal(row.get("shipping-tax")),
            gift_wrap_price=parse_decimal(row.get("gift-wrap-price")),
            gift_wrap_tax=parse_decimal(row.get("gift-wrap-tax")),
            item_promotion_discount=parse_decimal(row.get("item-promotion-discount")),
            ship_promotion_discount=parse_decimal(row.get("ship-promotion-discount")),
            ship_city=empty_to_none(row.get("ship-city")),
            ship_state=empty_to_none(row.get("ship-state")),
            ship_postal_code=empty_to_none(row.get("ship-postal-code")),
            ship_country=empty_to_none(row.get("ship-country")),
            promotion_ids=empty_to_none(row.get("promotion-ids")),
            is_business_order=parse_bool(row.get("is-business-order")),
            purchase_order_number=empty_to_none(row.get("purchase-order-number")),
            price_designation=empty_to_none(row.get("price-designation")),
            signature_confirmation_recommended=parse_bool(
                row.get("signature-confirmation-recommended")
            ),
            source_system="sp_api_reports",
            source_report_type=self.report_type,
            source_report_id=source_report_id,
            source_raw_file_path=source_raw_file_path,
            source_row_hash=compute_source_row_hash(row),
            raw_data=row,
        )
