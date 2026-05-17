from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from seller_data_pipeline.parsers.amazon.settlement_report_parser import (
    SETTLEMENT_V2_REPORT_TYPE,
    SETTLEMENT_V2_REQUIRED_FIELDS,
    SettlementV2TransactionRecord,
)

SETTLEMENT_TARGET_TABLE = "amazon_settlement_transaction"
SETTLEMENT_EXPECTED_FIELDS: tuple[str, ...] = tuple(sorted(SETTLEMENT_V2_REQUIRED_FIELDS))
SETTLEMENT_REQUIRED_FIELDS: tuple[str, ...] = SETTLEMENT_EXPECTED_FIELDS


@dataclass(frozen=True)
class SettlementTargetTableSpec:
    """Target-table mapping contract for GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2.

    Keep this contract aligned with docs/features/feature_settlement_ingestion.md,
    docs/database/database_current_schema_spec.md and sql/migrations/006_*.
    """

    report_type: str
    target_table: str
    business_key_fields: tuple[str, ...]
    table_columns: tuple[str, ...]
    expected_fields: tuple[str, ...]
    required_fields: tuple[str, ...]


SETTLEMENT_TARGET_TABLE_SPEC = SettlementTargetTableSpec(
    report_type=SETTLEMENT_V2_REPORT_TYPE,
    target_table=SETTLEMENT_TARGET_TABLE,
    business_key_fields=(
        "marketplace_id",
        "source_report_id",
        "source_raw_file_path",
        "source_row_index",
        "source_row_hash",
    ),
    table_columns=(
        "marketplace_id",
        "settlement_id",
        "settlement_start_date_raw",
        "settlement_end_date_raw",
        "deposit_date_raw",
        "total_amount",
        "currency",
        "is_settlement_summary",
        "transaction_type",
        "order_id",
        "merchant_order_id",
        "adjustment_id",
        "shipment_id",
        "marketplace_name",
        "amount_type",
        "amount_description",
        "amount",
        "amount_category",
        "profit_bucket",
        "fulfillment_id",
        "posted_date_raw",
        "posted_date_time_raw",
        "order_item_code",
        "merchant_order_item_id",
        "merchant_adjustment_item_id",
        "seller_sku",
        "quantity_purchased",
        "promotion_id",
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
    expected_fields=SETTLEMENT_EXPECTED_FIELDS,
    required_fields=SETTLEMENT_REQUIRED_FIELDS,
)


def map_settlement_record_to_table_row(
    record: SettlementV2TransactionRecord,
    *,
    source_row_index: int,
) -> dict[str, Any]:
    base_row = record.to_dict()
    base_row["source_report_request_id"] = None
    base_row["source_raw_file_id"] = None
    base_row["source_run_id"] = None
    base_row["source_row_index"] = source_row_index
    base_row["business_key_hash"] = compute_settlement_business_key_hash(row=base_row)
    base_row["raw_data"] = _json_dumps(base_row.get("raw_data", {}))
    return {
        column: _json_ready(base_row.get(column))
        for column in SETTLEMENT_TARGET_TABLE_SPEC.table_columns
    }


def compute_settlement_business_key_hash(*, row: dict[str, Any]) -> str:
    return compute_business_key_hash(
        target_table=SETTLEMENT_TARGET_TABLE_SPEC.target_table,
        business_key_fields=SETTLEMENT_TARGET_TABLE_SPEC.business_key_fields,
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
    "SETTLEMENT_EXPECTED_FIELDS",
    "SETTLEMENT_REQUIRED_FIELDS",
    "SETTLEMENT_TARGET_TABLE",
    "SETTLEMENT_TARGET_TABLE_SPEC",
    "SettlementTargetTableSpec",
    "compute_business_key_hash",
    "compute_settlement_business_key_hash",
    "map_settlement_record_to_table_row",
    "read_jsonl",
    "write_jsonl",
]
