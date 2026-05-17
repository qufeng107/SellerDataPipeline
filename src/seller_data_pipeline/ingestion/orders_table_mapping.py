from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from seller_data_pipeline.parsers.amazon.orders_report_parser import (
    ALL_ORDERS_REPORT_TYPE,
    ALL_ORDERS_REQUIRED_FIELDS,
    AllOrdersItemRecord,
)

ORDERS_TARGET_TABLE = "amazon_order_item"
ORDERS_EXPECTED_FIELDS: tuple[str, ...] = (
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
)
ORDERS_REQUIRED_FIELDS: tuple[str, ...] = tuple(sorted(ALL_ORDERS_REQUIRED_FIELDS))


@dataclass(frozen=True)
class OrdersTargetTableSpec:
    """Target-table mapping contract for GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL.

    Keep this contract aligned with docs/features/feature_orders_ingestion.md,
    docs/database/database_current_schema_spec.md and sql/migrations/007_*.
    """

    report_type: str
    target_table: str
    business_key_fields: tuple[str, ...]
    table_columns: tuple[str, ...]
    expected_fields: tuple[str, ...]
    required_fields: tuple[str, ...]


ORDERS_TARGET_TABLE_SPEC = OrdersTargetTableSpec(
    report_type=ALL_ORDERS_REPORT_TYPE,
    target_table=ORDERS_TARGET_TABLE,
    business_key_fields=(
        "marketplace_id",
        "source_report_type",
        "amazon_order_id",
        "seller_sku",
        "asin",
        "purchase_date_raw",
    ),
    table_columns=(
        "marketplace_id",
        "amazon_order_id",
        "merchant_order_id",
        "purchase_date_raw",
        "last_updated_date_raw",
        "order_status",
        "fulfillment_channel",
        "sales_channel",
        "order_channel",
        "ship_service_level",
        "product_name",
        "seller_sku",
        "asin",
        "item_status",
        "quantity",
        "currency",
        "item_price",
        "item_tax",
        "shipping_price",
        "shipping_tax",
        "gift_wrap_price",
        "gift_wrap_tax",
        "item_promotion_discount",
        "ship_promotion_discount",
        "ship_city",
        "ship_state",
        "ship_postal_code",
        "ship_country",
        "promotion_ids",
        "is_business_order",
        "purchase_order_number",
        "price_designation",
        "signature_confirmation_recommended",
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
    expected_fields=ORDERS_EXPECTED_FIELDS,
    required_fields=ORDERS_REQUIRED_FIELDS,
)


def map_orders_record_to_table_row(
    record: AllOrdersItemRecord,
    *,
    source_row_index: int,
) -> dict[str, Any]:
    """Map one parsed orders row to a DB-ready Azure SQL row dict."""

    base_row = record.to_dict()
    base_row["source_report_request_id"] = None
    base_row["source_raw_file_id"] = None
    base_row["source_run_id"] = None
    base_row["source_row_index"] = source_row_index
    base_row["business_key_hash"] = compute_orders_business_key_hash(row=base_row)
    base_row["raw_data"] = _json_dumps(base_row.get("raw_data", {}))
    return {
        column: _json_ready(base_row.get(column))
        for column in ORDERS_TARGET_TABLE_SPEC.table_columns
    }


def compute_orders_business_key_hash(*, row: dict[str, Any]) -> str:
    return compute_business_key_hash(
        target_table=ORDERS_TARGET_TABLE_SPEC.target_table,
        business_key_fields=ORDERS_TARGET_TABLE_SPEC.business_key_fields,
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
    "ORDERS_EXPECTED_FIELDS",
    "ORDERS_REQUIRED_FIELDS",
    "ORDERS_TARGET_TABLE",
    "ORDERS_TARGET_TABLE_SPEC",
    "OrdersTargetTableSpec",
    "compute_business_key_hash",
    "compute_orders_business_key_hash",
    "map_orders_record_to_table_row",
    "read_jsonl",
    "write_jsonl",
]
