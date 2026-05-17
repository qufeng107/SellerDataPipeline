from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from seller_data_pipeline.parsers.amazon.listings_all_data_parser import ListingSnapshotRecord

LISTING_REPORT_TYPE = "GET_MERCHANT_LISTINGS_ALL_DATA"
LISTING_TARGET_TABLE = "amazon_listing_snapshot"

LISTING_EXPECTED_FIELDS: tuple[str, ...] = (
    "item-name",
    "item-description",
    "listing-id",
    "seller-sku",
    "price",
    "quantity",
    "open-date",
    "image-url",
    "item-is-marketplace",
    "product-id-type",
    "zshop-shipping-fee",
    "item-note",
    "item-condition",
    "zshop-category1",
    "zshop-browse-path",
    "zshop-storefront-feature",
    "asin1",
    "asin2",
    "asin3",
    "will-ship-internationally",
    "expedited-shipping",
    "zshop-boldface",
    "product-id",
    "bid-for-featured-placement",
    "add-delete",
    "pending-quantity",
    "fulfillment-channel",
    "merchant-shipping-group",
    "status",
)

LISTING_REQUIRED_FIELDS: tuple[str, ...] = (
    "listing-id",
    "seller-sku",
    "asin1",
    "product-id",
    "product-id-type",
    "item-name",
    "price",
    "open-date",
    "item-condition",
    "fulfillment-channel",
    "status",
)


@dataclass(frozen=True)
class ListingTargetTableSpec:
    """Target-table mapping contract for GET_MERCHANT_LISTINGS_ALL_DATA.

    Keep this contract aligned with docs/features/feature_listing_snapshot_ingestion.md,
    docs/database/database_current_schema_spec.md and sql/migrations/003_*.
    """

    report_type: str
    target_table: str
    business_key_fields: tuple[str, ...]
    table_columns: tuple[str, ...]
    expected_fields: tuple[str, ...]
    required_fields: tuple[str, ...]


LISTING_TARGET_TABLE_SPEC = ListingTargetTableSpec(
    report_type=LISTING_REPORT_TYPE,
    target_table=LISTING_TARGET_TABLE,
    business_key_fields=("marketplace_id", "snapshot_date", "seller_sku", "listing_id"),
    table_columns=(
        "marketplace_id",
        "snapshot_date",
        "listing_id",
        "seller_sku",
        "asin",
        "product_id",
        "product_id_type",
        "item_name",
        "item_description",
        "price",
        "currency",
        "quantity",
        "pending_quantity",
        "open_date_raw",
        "open_date_utc",
        "item_is_marketplace",
        "item_condition",
        "fulfillment_channel",
        "merchant_shipping_group",
        "status",
        "source_system",
        "source_report_type",
        "source_report_id",
        "source_report_request_id",
        "source_raw_file_id",
        "source_raw_file_path",
        "source_run_id",
        "source_row_hash",
        "business_key_hash",
        "raw_data",
    ),
    expected_fields=LISTING_EXPECTED_FIELDS,
    required_fields=LISTING_REQUIRED_FIELDS,
)


def map_listing_record_to_table_row(record: ListingSnapshotRecord) -> dict[str, Any]:
    """Map one parsed listing record to a DB-ready row dict.

    The output uses database column names and JSON-serializable values, so it can be written to a
    preview JSONL file and later passed to repository/upsert code without reparsing the raw file.
    """

    base_row = record.to_dict()
    base_row["open_date_utc"] = None
    base_row["source_report_request_id"] = None
    base_row["source_raw_file_id"] = None
    base_row["source_run_id"] = None
    base_row["business_key_hash"] = compute_listing_business_key_hash(base_row)
    base_row["raw_data"] = _json_dumps(base_row.get("raw_data", {}))
    return {
        column: _json_ready(base_row.get(column))
        for column in LISTING_TARGET_TABLE_SPEC.table_columns
    }


def compute_listing_business_key_hash(row: dict[str, Any]) -> str:
    return compute_business_key_hash(
        target_table=LISTING_TARGET_TABLE_SPEC.target_table,
        business_key_fields=LISTING_TARGET_TABLE_SPEC.business_key_fields,
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
    "LISTING_EXPECTED_FIELDS",
    "LISTING_REPORT_TYPE",
    "LISTING_REQUIRED_FIELDS",
    "LISTING_TARGET_TABLE",
    "LISTING_TARGET_TABLE_SPEC",
    "ListingTargetTableSpec",
    "compute_business_key_hash",
    "compute_listing_business_key_hash",
    "map_listing_record_to_table_row",
    "read_jsonl",
    "write_jsonl",
]
