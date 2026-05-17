from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from seller_data_pipeline.parsers.amazon.flat_file_utils import (
    AmazonFlatFileParser,
    compute_source_row_hash,
    empty_to_none,
    parse_decimal,
    parse_int,
    serialize_decimals,
)

RESTOCK_INVENTORY_REPORT_TYPE = "GET_RESTOCK_INVENTORY_RECOMMENDATIONS_REPORT"

RESTOCK_INVENTORY_REQUIRED_FIELDS = {
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

_DECIMAL_FIELDS = {"price", "sales_last_30_days", "unit_storage_size"}


@dataclass(frozen=True)
class RestockInventoryRecommendationRecord:
    marketplace_id: str
    country: str | None
    product_name: str | None
    fnsku: str | None
    seller_sku: str | None
    asin: str | None
    condition: str | None
    supplier: str | None
    supplier_part_no: str | None
    currency_code: str | None
    price: Decimal | None
    sales_last_30_days: Decimal | None
    units_sold_last_30_days: int | None
    total_units: int | None
    inbound_quantity: int | None
    available_quantity: int | None
    fc_transfer_quantity: int | None
    fc_processing_quantity: int | None
    customer_order_quantity: int | None
    unfulfillable_quantity: int | None
    working_quantity: int | None
    shipped_quantity: int | None
    receiving_quantity: int | None
    fulfilled_by: str | None
    total_days_of_supply: int | None
    days_of_supply_at_amazon_fulfillment_network: int | None
    alert: str | None
    recommended_replenishment_quantity: int | None
    recommended_ship_date_raw: str | None
    recommended_action: str | None
    unit_storage_size: Decimal | None
    source_system: str
    source_report_type: str
    source_report_id: str | None
    source_raw_file_path: str | None
    source_row_hash: str
    raw_data: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return serialize_decimals(asdict(self), _DECIMAL_FIELDS)


class RestockInventoryRecommendationsParser(AmazonFlatFileParser):
    """Parser for GET_RESTOCK_INVENTORY_RECOMMENDATIONS_REPORT reports."""

    report_type = RESTOCK_INVENTORY_REPORT_TYPE
    required_fields = RESTOCK_INVENTORY_REQUIRED_FIELDS

    def row_to_record(
        self,
        *,
        row: dict[str, str],
        marketplace_id: str,
        source_report_id: str | None,
        source_raw_file_path: str | None,
    ) -> RestockInventoryRecommendationRecord:
        return RestockInventoryRecommendationRecord(
            marketplace_id=marketplace_id,
            country=empty_to_none(row.get("Country")),
            product_name=empty_to_none(row.get("Product Name")),
            fnsku=empty_to_none(row.get("FNSKU")),
            seller_sku=empty_to_none(row.get("Merchant SKU")),
            asin=empty_to_none(row.get("ASIN")),
            condition=empty_to_none(row.get("Condition")),
            supplier=empty_to_none(row.get("Supplier")),
            supplier_part_no=empty_to_none(row.get("Supplier part no.")),
            currency_code=empty_to_none(row.get("Currency code")),
            price=parse_decimal(row.get("Price")),
            sales_last_30_days=parse_decimal(row.get("Sales last 30 days")),
            units_sold_last_30_days=parse_int(row.get("Units Sold Last 30 Days")),
            total_units=parse_int(row.get("Total Units")),
            inbound_quantity=parse_int(row.get("Inbound")),
            available_quantity=parse_int(row.get("Available")),
            fc_transfer_quantity=parse_int(row.get("FC transfer")),
            fc_processing_quantity=parse_int(row.get("FC Processing")),
            customer_order_quantity=parse_int(row.get("Customer Order")),
            unfulfillable_quantity=parse_int(row.get("Unfulfillable")),
            working_quantity=parse_int(row.get("Working")),
            shipped_quantity=parse_int(row.get("Shipped")),
            receiving_quantity=parse_int(row.get("Receiving")),
            fulfilled_by=empty_to_none(row.get("Fulfilled by")),
            total_days_of_supply=parse_int(
                row.get("Total Days of Supply (including units from open shipments)")
            ),
            days_of_supply_at_amazon_fulfillment_network=parse_int(
                row.get("Days of Supply at Amazon Fulfillment Network")
            ),
            alert=empty_to_none(row.get("Alert")),
            recommended_replenishment_quantity=parse_int(row.get("Recommended replenishment qty")),
            recommended_ship_date_raw=empty_to_none(row.get("Recommended ship date")),
            recommended_action=empty_to_none(row.get("Recommended action")),
            unit_storage_size=parse_decimal(row.get("Unit storage size")),
            source_system="sp_api_reports",
            source_report_type=self.report_type,
            source_report_id=source_report_id,
            source_raw_file_path=source_raw_file_path,
            source_row_hash=compute_source_row_hash(row),
            raw_data=row,
        )
