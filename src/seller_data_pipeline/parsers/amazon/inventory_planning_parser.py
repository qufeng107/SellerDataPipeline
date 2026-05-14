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

FBA_INVENTORY_PLANNING_REPORT_TYPE = "GET_FBA_INVENTORY_PLANNING_DATA"

FBA_INVENTORY_PLANNING_REQUIRED_FIELDS = {
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
    "currency",
    "units-shipped-t7",
    "units-shipped-t30",
    "alert",
    "your-price",
    "recommended-action",
    "sell-through",
    "storage-type",
    "marketplace",
    "days-of-supply",
    "estimated-excess-quantity",
}

_DECIMAL_FIELDS = {
    "your_price",
    "sales_price",
    "recommended_sales_price",
    "estimated_cost_savings_of_recommended_actions",
    "sell_through",
    "item_volume",
    "storage_volume",
    "days_of_supply",
}


@dataclass(frozen=True)
class FbaInventoryPlanningRecord:
    marketplace_id: str
    snapshot_date_raw: str | None
    seller_sku: str | None
    fnsku: str | None
    asin: str | None
    product_name: str | None
    condition: str | None
    available_quantity: int | None
    pending_removal_quantity: int | None
    inv_age_0_to_90_days: int | None
    inv_age_91_to_180_days: int | None
    inv_age_181_to_270_days: int | None
    inv_age_271_to_365_days: int | None
    inv_age_366_to_455_days: int | None
    inv_age_456_plus_days: int | None
    currency: str | None
    units_shipped_t7: int | None
    units_shipped_t30: int | None
    units_shipped_t60: int | None
    units_shipped_t90: int | None
    alert: str | None
    your_price: Decimal | None
    sales_price: Decimal | None
    recommended_action: str | None
    recommended_sales_price: Decimal | None
    recommended_sale_duration_days: int | None
    recommended_removal_quantity: int | None
    estimated_cost_savings_of_recommended_actions: Decimal | None
    sell_through: Decimal | None
    item_volume: Decimal | None
    volume_unit_measurement: str | None
    storage_type: str | None
    storage_volume: Decimal | None
    marketplace_name: str | None
    product_group: str | None
    sales_rank: int | None
    days_of_supply: Decimal | None
    estimated_excess_quantity: int | None
    source_system: str
    source_report_type: str
    source_report_id: str | None
    source_raw_file_path: str | None
    source_row_hash: str
    raw_data: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return serialize_decimals(payload, _DECIMAL_FIELDS)


class FbaInventoryPlanningParser(AmazonFlatFileParser):
    """Parser for GET_FBA_INVENTORY_PLANNING_DATA reports."""

    report_type = FBA_INVENTORY_PLANNING_REPORT_TYPE
    required_fields = FBA_INVENTORY_PLANNING_REQUIRED_FIELDS

    def row_to_record(
        self,
        *,
        row: dict[str, str],
        marketplace_id: str,
        source_report_id: str | None,
        source_raw_file_path: str | None,
    ) -> FbaInventoryPlanningRecord:
        return FbaInventoryPlanningRecord(
            marketplace_id=marketplace_id,
            snapshot_date_raw=empty_to_none(row.get("snapshot-date")),
            seller_sku=empty_to_none(row.get("sku")),
            fnsku=empty_to_none(row.get("fnsku")),
            asin=empty_to_none(row.get("asin")),
            product_name=empty_to_none(row.get("product-name")),
            condition=empty_to_none(row.get("condition")),
            available_quantity=parse_int(row.get("available")),
            pending_removal_quantity=parse_int(row.get("pending-removal-quantity")),
            inv_age_0_to_90_days=parse_int(row.get("inv-age-0-to-90-days")),
            inv_age_91_to_180_days=parse_int(row.get("inv-age-91-to-180-days")),
            inv_age_181_to_270_days=parse_int(row.get("inv-age-181-to-270-days")),
            inv_age_271_to_365_days=parse_int(row.get("inv-age-271-to-365-days")),
            inv_age_366_to_455_days=parse_int(row.get("inv-age-366-to-455-days")),
            inv_age_456_plus_days=parse_int(row.get("inv-age-456-plus-days")),
            currency=empty_to_none(row.get("currency")),
            units_shipped_t7=parse_int(row.get("units-shipped-t7")),
            units_shipped_t30=parse_int(row.get("units-shipped-t30")),
            units_shipped_t60=parse_int(row.get("units-shipped-t60")),
            units_shipped_t90=parse_int(row.get("units-shipped-t90")),
            alert=empty_to_none(row.get("alert")),
            your_price=parse_decimal(row.get("your-price")),
            sales_price=parse_decimal(row.get("sales-price")),
            recommended_action=empty_to_none(row.get("recommended-action")),
            recommended_sales_price=parse_decimal(row.get("recommended-sales-price")),
            recommended_sale_duration_days=parse_int(row.get("recommended-sale-duration-days")),
            recommended_removal_quantity=parse_int(row.get("recommended-removal-quantity")),
            estimated_cost_savings_of_recommended_actions=parse_decimal(
                row.get("estimated-cost-savings-of-recommended-actions")
            ),
            sell_through=parse_decimal(row.get("sell-through")),
            item_volume=parse_decimal(row.get("item-volume")),
            volume_unit_measurement=empty_to_none(row.get("volume-unit-measurement")),
            storage_type=empty_to_none(row.get("storage-type")),
            storage_volume=parse_decimal(row.get("storage-volume")),
            marketplace_name=empty_to_none(row.get("marketplace")),
            product_group=empty_to_none(row.get("product-group")),
            sales_rank=parse_int(row.get("sales-rank")),
            days_of_supply=parse_decimal(row.get("days-of-supply")),
            estimated_excess_quantity=parse_int(row.get("estimated-excess-quantity")),
            source_system="sp_api_reports",
            source_report_type=self.report_type,
            source_report_id=source_report_id,
            source_raw_file_path=source_raw_file_path,
            source_row_hash=compute_source_row_hash(row),
            raw_data=row,
        )
