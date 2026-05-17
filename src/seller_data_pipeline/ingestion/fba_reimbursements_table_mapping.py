from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from seller_data_pipeline.parsers.amazon.fba_reimbursements_parser import (
    FBA_REIMBURSEMENTS_REPORT_TYPE,
    FBA_REIMBURSEMENTS_REQUIRED_FIELDS as PARSER_REQUIRED_FIELDS,
    FbaReimbursementRecord,
)

FBA_REIMBURSEMENTS_TARGET_TABLE = "amazon_fba_reimbursement"
FBA_REIMBURSEMENTS_EXPECTED_FIELDS: tuple[str, ...] = (
    "approval-date",
    "reimbursement-id",
    "case-id",
    "amazon-order-id",
    "reason",
    "sku",
    "fnsku",
    "asin",
    "product-name",
    "condition",
    "currency-unit",
    "amount-per-unit",
    "amount-total",
    "quantity-reimbursed-cash",
    "quantity-reimbursed-inventory",
    "quantity-reimbursed-total",
    "original-reimbursement-id",
    "original-reimbursement-type",
)
FBA_REIMBURSEMENTS_REQUIRED_FIELDS: tuple[str, ...] = tuple(
    sorted(PARSER_REQUIRED_FIELDS)
)


@dataclass(frozen=True)
class FbaReimbursementsTargetTableSpec:
    """Target-table mapping contract for GET_FBA_REIMBURSEMENTS_DATA.

    Keep this contract aligned with docs/features/feature_fba_reimbursements_ingestion.md,
    docs/database/database_current_schema_spec.md and sql/migrations/008_*.
    """

    report_type: str
    target_table: str
    business_key_fields: tuple[str, ...]
    table_columns: tuple[str, ...]
    expected_fields: tuple[str, ...]
    required_fields: tuple[str, ...]


FBA_REIMBURSEMENTS_TARGET_TABLE_SPEC = FbaReimbursementsTargetTableSpec(
    report_type=FBA_REIMBURSEMENTS_REPORT_TYPE,
    target_table=FBA_REIMBURSEMENTS_TARGET_TABLE,
    business_key_fields=(
        "marketplace_id",
        "source_report_type",
        "reimbursement_id",
        "seller_sku",
        "fnsku",
        "asin",
        "approval_date_raw",
        "amount_total",
        "quantity_reimbursed_total",
    ),
    table_columns=(
        "marketplace_id",
        "approval_date_raw",
        "reimbursement_id",
        "case_id",
        "amazon_order_id",
        "reason",
        "seller_sku",
        "fnsku",
        "asin",
        "product_name",
        "condition",
        "currency",
        "amount_per_unit",
        "amount_total",
        "quantity_reimbursed_cash",
        "quantity_reimbursed_inventory",
        "quantity_reimbursed_total",
        "original_reimbursement_id",
        "original_reimbursement_type",
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
    expected_fields=FBA_REIMBURSEMENTS_EXPECTED_FIELDS,
    required_fields=FBA_REIMBURSEMENTS_REQUIRED_FIELDS,
)


def map_fba_reimbursement_record_to_table_row(
    record: FbaReimbursementRecord,
    *,
    source_row_index: int,
) -> dict[str, Any]:
    """Map one parsed FBA reimbursement row to a DB-ready Azure SQL row dict."""

    base_row = record.to_dict()
    base_row["source_report_request_id"] = None
    base_row["source_raw_file_id"] = None
    base_row["source_run_id"] = None
    base_row["source_row_index"] = source_row_index
    base_row["business_key_hash"] = compute_fba_reimbursement_business_key_hash(row=base_row)
    base_row["raw_data"] = _json_dumps(base_row.get("raw_data", {}))
    return {
        column: _json_ready(base_row.get(column))
        for column in FBA_REIMBURSEMENTS_TARGET_TABLE_SPEC.table_columns
    }


def compute_fba_reimbursement_business_key_hash(*, row: dict[str, Any]) -> str:
    return compute_business_key_hash(
        target_table=FBA_REIMBURSEMENTS_TARGET_TABLE_SPEC.target_table,
        business_key_fields=FBA_REIMBURSEMENTS_TARGET_TABLE_SPEC.business_key_fields,
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
    "FBA_REIMBURSEMENTS_EXPECTED_FIELDS",
    "FBA_REIMBURSEMENTS_REQUIRED_FIELDS",
    "FBA_REIMBURSEMENTS_TARGET_TABLE",
    "FBA_REIMBURSEMENTS_TARGET_TABLE_SPEC",
    "FbaReimbursementsTargetTableSpec",
    "compute_business_key_hash",
    "compute_fba_reimbursement_business_key_hash",
    "map_fba_reimbursement_record_to_table_row",
    "read_jsonl",
    "write_jsonl",
]
