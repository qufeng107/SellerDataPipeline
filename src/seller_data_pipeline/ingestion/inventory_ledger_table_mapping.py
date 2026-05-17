from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from seller_data_pipeline.parsers.amazon.inventory_ledger_parser import (
    LEDGER_DETAIL_REPORT_TYPE,
    LEDGER_DETAIL_REQUIRED_FIELDS,
    LEDGER_SUMMARY_REPORT_TYPE,
    LEDGER_SUMMARY_REQUIRED_FIELDS,
    InventoryLedgerDetailRecord,
    InventoryLedgerSummaryRecord,
)

LEDGER_SUMMARY_TARGET_TABLE = "amazon_inventory_ledger_summary_daily"
LEDGER_DETAIL_TARGET_TABLE = "amazon_inventory_ledger_detail"

LEDGER_SUMMARY_EXPECTED_FIELDS: tuple[str, ...] = tuple(sorted(LEDGER_SUMMARY_REQUIRED_FIELDS))
LEDGER_SUMMARY_REQUIRED_FIELDS_TUPLE: tuple[str, ...] = tuple(
    sorted(LEDGER_SUMMARY_REQUIRED_FIELDS)
)

LEDGER_DETAIL_EXPECTED_FIELDS: tuple[str, ...] = tuple(sorted(LEDGER_DETAIL_REQUIRED_FIELDS))
LEDGER_DETAIL_REQUIRED_FIELDS_TUPLE: tuple[str, ...] = tuple(sorted(LEDGER_DETAIL_REQUIRED_FIELDS))


@dataclass(frozen=True)
class InventoryLedgerTargetTableSpec:
    report_type: str
    target_table: str
    business_key_fields: tuple[str, ...]
    table_columns: tuple[str, ...]
    expected_fields: tuple[str, ...]
    required_fields: tuple[str, ...]


LEDGER_SUMMARY_TARGET_TABLE_SPEC = InventoryLedgerTargetTableSpec(
    report_type=LEDGER_SUMMARY_REPORT_TYPE,
    target_table=LEDGER_SUMMARY_TARGET_TABLE,
    business_key_fields=(
        "marketplace_id",
        "source_report_type",
        "ledger_date_raw",
        "seller_sku",
        "fnsku",
        "asin",
        "disposition",
        "location",
        "store",
    ),
    table_columns=(
        "marketplace_id",
        "ledger_date_raw",
        "fnsku",
        "asin",
        "seller_sku",
        "title",
        "disposition",
        "starting_warehouse_balance",
        "in_transit_between_warehouses",
        "receipts",
        "customer_shipments",
        "customer_returns",
        "vendor_returns",
        "warehouse_transfer_in_out",
        "found",
        "lost",
        "damaged",
        "disposed",
        "other_events",
        "ending_warehouse_balance",
        "unknown_events",
        "location",
        "store",
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
    expected_fields=LEDGER_SUMMARY_EXPECTED_FIELDS,
    required_fields=LEDGER_SUMMARY_REQUIRED_FIELDS_TUPLE,
)

LEDGER_DETAIL_TARGET_TABLE_SPEC = InventoryLedgerTargetTableSpec(
    report_type=LEDGER_DETAIL_REPORT_TYPE,
    target_table=LEDGER_DETAIL_TARGET_TABLE,
    business_key_fields=(
        "marketplace_id",
        "source_report_type",
        "date_time_raw",
        "seller_sku",
        "fnsku",
        "asin",
        "event_type",
        "reference_id",
        "fulfillment_center",
        "disposition",
        "quantity",
        "source_row_index",
    ),
    table_columns=(
        "marketplace_id",
        "ledger_date_raw",
        "fnsku",
        "asin",
        "seller_sku",
        "title",
        "event_type",
        "reference_id",
        "quantity",
        "fulfillment_center",
        "disposition",
        "reason",
        "country",
        "reconciled_quantity",
        "unreconciled_quantity",
        "date_time_raw",
        "store",
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
    expected_fields=LEDGER_DETAIL_EXPECTED_FIELDS,
    required_fields=LEDGER_DETAIL_REQUIRED_FIELDS_TUPLE,
)

INVENTORY_LEDGER_TARGET_TABLE_SPECS: tuple[InventoryLedgerTargetTableSpec, ...] = (
    LEDGER_SUMMARY_TARGET_TABLE_SPEC,
    LEDGER_DETAIL_TARGET_TABLE_SPEC,
)


def get_inventory_ledger_target_table_spec(
    target_table: str,
) -> InventoryLedgerTargetTableSpec | None:
    for spec in INVENTORY_LEDGER_TARGET_TABLE_SPECS:
        if spec.target_table == target_table:
            return spec
    return None


def map_inventory_ledger_summary_record_to_table_row(
    record: InventoryLedgerSummaryRecord,
    *,
    source_row_index: int,
) -> dict[str, Any]:
    return _prepare_row(
        record.to_dict(),
        source_row_index=source_row_index,
        table_spec=LEDGER_SUMMARY_TARGET_TABLE_SPEC,
    )


def map_inventory_ledger_detail_record_to_table_row(
    record: InventoryLedgerDetailRecord,
    *,
    source_row_index: int,
) -> dict[str, Any]:
    return _prepare_row(
        record.to_dict(),
        source_row_index=source_row_index,
        table_spec=LEDGER_DETAIL_TARGET_TABLE_SPEC,
    )


def compute_inventory_ledger_business_key_hash(
    *,
    row: dict[str, Any],
    table_spec: InventoryLedgerTargetTableSpec,
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


def _prepare_row(
    base_row: dict[str, Any],
    *,
    source_row_index: int,
    table_spec: InventoryLedgerTargetTableSpec,
) -> dict[str, Any]:
    row = dict(base_row)
    row["source_report_request_id"] = None
    row["source_raw_file_id"] = None
    row["source_run_id"] = None
    row["source_row_index"] = source_row_index
    row["business_key_hash"] = compute_inventory_ledger_business_key_hash(
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
    "INVENTORY_LEDGER_TARGET_TABLE_SPECS",
    "LEDGER_DETAIL_EXPECTED_FIELDS",
    "LEDGER_DETAIL_REQUIRED_FIELDS_TUPLE",
    "LEDGER_DETAIL_TARGET_TABLE",
    "LEDGER_DETAIL_TARGET_TABLE_SPEC",
    "LEDGER_SUMMARY_EXPECTED_FIELDS",
    "LEDGER_SUMMARY_REQUIRED_FIELDS_TUPLE",
    "LEDGER_SUMMARY_TARGET_TABLE",
    "LEDGER_SUMMARY_TARGET_TABLE_SPEC",
    "InventoryLedgerTargetTableSpec",
    "compute_business_key_hash",
    "compute_inventory_ledger_business_key_hash",
    "get_inventory_ledger_target_table_spec",
    "map_inventory_ledger_detail_record_to_table_row",
    "map_inventory_ledger_summary_record_to_table_row",
    "read_jsonl",
    "write_jsonl",
]
