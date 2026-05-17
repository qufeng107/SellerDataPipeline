from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from seller_data_pipeline.parsers.amazon.fba_inventory_parser import FbaInventorySnapshotRecord

INVENTORY_REPORT_TYPE = "GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA"
INVENTORY_TARGET_TABLE = "amazon_inventory_daily"

INVENTORY_EXPECTED_FIELDS: tuple[str, ...] = (
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
)

INVENTORY_REQUIRED_FIELDS: tuple[str, ...] = INVENTORY_EXPECTED_FIELDS


@dataclass(frozen=True)
class InventoryTargetTableSpec:
    """Target-table mapping contract for GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA.

    Keep this contract aligned with docs/features/feature_inventory_ingestion.md,
    docs/database/database_current_schema_spec.md and sql/migrations/004_*.
    """

    report_type: str
    target_table: str
    business_key_fields: tuple[str, ...]
    table_columns: tuple[str, ...]
    expected_fields: tuple[str, ...]
    required_fields: tuple[str, ...]


INVENTORY_TARGET_TABLE_SPEC = InventoryTargetTableSpec(
    report_type=INVENTORY_REPORT_TYPE,
    target_table=INVENTORY_TARGET_TABLE,
    business_key_fields=("marketplace_id", "snapshot_date", "seller_sku", "fnsku", "asin"),
    table_columns=(
        "marketplace_id",
        "snapshot_date",
        "seller_sku",
        "fnsku",
        "asin",
        "product_name",
        "condition",
        "your_price",
        "currency",
        "mfn_listing_exists",
        "mfn_fulfillable_quantity",
        "afn_listing_exists",
        "afn_warehouse_quantity",
        "afn_fulfillable_quantity",
        "afn_unsellable_quantity",
        "afn_reserved_quantity",
        "afn_total_quantity",
        "per_unit_volume",
        "afn_inbound_working_quantity",
        "afn_inbound_shipped_quantity",
        "afn_inbound_receiving_quantity",
        "afn_researching_quantity",
        "afn_reserved_future_supply",
        "afn_future_supply_buyable",
        "store",
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
    expected_fields=INVENTORY_EXPECTED_FIELDS,
    required_fields=INVENTORY_REQUIRED_FIELDS,
)


def map_inventory_record_to_table_row(record: FbaInventorySnapshotRecord) -> dict[str, Any]:
    """Map one parsed FBA inventory record to a DB-ready row dict."""

    base_row = record.to_dict()
    base_row["source_report_request_id"] = None
    base_row["source_raw_file_id"] = None
    base_row["source_run_id"] = None
    base_row["business_key_hash"] = compute_inventory_business_key_hash(base_row)
    base_row["raw_data"] = _json_dumps(base_row.get("raw_data", {}))
    return {
        column: _json_ready(base_row.get(column))
        for column in INVENTORY_TARGET_TABLE_SPEC.table_columns
    }


def compute_inventory_business_key_hash(row: dict[str, Any]) -> str:
    return compute_business_key_hash(
        target_table=INVENTORY_TARGET_TABLE_SPEC.target_table,
        business_key_fields=INVENTORY_TARGET_TABLE_SPEC.business_key_fields,
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
        "business_key": {
            field: _json_ready(row.get(field)) for field in business_key_fields
        },
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
    "INVENTORY_EXPECTED_FIELDS",
    "INVENTORY_REPORT_TYPE",
    "INVENTORY_REQUIRED_FIELDS",
    "INVENTORY_TARGET_TABLE",
    "INVENTORY_TARGET_TABLE_SPEC",
    "InventoryTargetTableSpec",
    "compute_business_key_hash",
    "compute_inventory_business_key_hash",
    "map_inventory_record_to_table_row",
    "read_jsonl",
    "write_jsonl",
]
