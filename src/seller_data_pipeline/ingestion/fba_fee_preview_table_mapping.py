from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from seller_data_pipeline.parsers.amazon.fba_estimated_fees_parser import (
    FBA_ESTIMATED_FEES_REPORT_TYPE,
    FbaEstimatedFeeRecord,
)
from seller_data_pipeline.parsers.amazon.fba_estimated_fees_parser import (
    FBA_ESTIMATED_FEES_REQUIRED_FIELDS as PARSER_REQUIRED_FIELDS,
)

FBA_FEE_PREVIEW_TARGET_TABLE = "amazon_fba_fee_preview"
FBA_FEE_PREVIEW_EXPECTED_FIELDS: tuple[str, ...] = (
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
    "longest-side",
    "median-side",
    "shortest-side",
    "length-and-girth",
    "unit-of-dimension",
    "item-package-weight",
    "unit-of-weight",
    "product-size-tier",
    "currency",
    "estimated-fee-total",
    "estimated-referral-fee-per-unit",
    "estimated-variable-closing-fee",
    "estimated-order-handling-fee-per-order",
    "estimated-pick-pack-fee-per-unit",
    "estimated-weight-handling-fee-per-unit",
    "expected-fulfillment-fee-per-unit",
    "estimated-future-fee (Current Selling on Amazon + Future Fulfillment fees)",
    "estimated-future-order-handling-fee-per-order",
    "estimated-future-pick-pack-fee-per-unit",
    "estimated-future-weight-handling-fee-per-unit",
    "expected-future-fulfillment-fee-per-unit",
)
FBA_FEE_PREVIEW_REQUIRED_FIELDS: tuple[str, ...] = tuple(sorted(PARSER_REQUIRED_FIELDS))


@dataclass(frozen=True)
class FbaFeePreviewTargetTableSpec:
    """Target-table mapping contract for GET_FBA_ESTIMATED_FBA_FEES_TXT_DATA.

    Keep this contract aligned with docs/features/feature_fba_fee_preview_ingestion.md,
    docs/database/database_current_schema_spec.md and sql/migrations/009_*.
    """

    report_type: str
    target_table: str
    business_key_fields: tuple[str, ...]
    table_columns: tuple[str, ...]
    expected_fields: tuple[str, ...]
    required_fields: tuple[str, ...]


FBA_FEE_PREVIEW_TARGET_TABLE_SPEC = FbaFeePreviewTargetTableSpec(
    report_type=FBA_ESTIMATED_FEES_REPORT_TYPE,
    target_table=FBA_FEE_PREVIEW_TARGET_TABLE,
    business_key_fields=(
        "marketplace_id",
        "source_report_type",
        "seller_sku",
        "fnsku",
        "asin",
        "amazon_store",
        "currency",
        "product_size_tier",
        "your_price",
        "sales_price",
    ),
    table_columns=(
        "marketplace_id",
        "seller_sku",
        "fnsku",
        "asin",
        "amazon_store",
        "product_name",
        "product_group",
        "brand",
        "fulfilled_by",
        "your_price",
        "sales_price",
        "longest_side",
        "median_side",
        "shortest_side",
        "length_and_girth",
        "unit_of_dimension",
        "item_package_weight",
        "unit_of_weight",
        "product_size_tier",
        "currency",
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
    expected_fields=FBA_FEE_PREVIEW_EXPECTED_FIELDS,
    required_fields=FBA_FEE_PREVIEW_REQUIRED_FIELDS,
)


def map_fba_fee_preview_record_to_table_row(
    record: FbaEstimatedFeeRecord,
    *,
    source_row_index: int,
) -> dict[str, Any]:
    """Map one parsed FBA fee preview row to a DB-ready Azure SQL row dict."""

    base_row = record.to_dict()
    base_row["source_report_request_id"] = None
    base_row["source_raw_file_id"] = None
    base_row["source_run_id"] = None
    base_row["source_row_index"] = source_row_index
    base_row["business_key_hash"] = compute_fba_fee_preview_business_key_hash(row=base_row)
    base_row["raw_data"] = _json_dumps(base_row.get("raw_data", {}))
    return {
        column: _json_ready(base_row.get(column))
        for column in FBA_FEE_PREVIEW_TARGET_TABLE_SPEC.table_columns
    }


def compute_fba_fee_preview_business_key_hash(*, row: dict[str, Any]) -> str:
    return compute_business_key_hash(
        target_table=FBA_FEE_PREVIEW_TARGET_TABLE_SPEC.target_table,
        business_key_fields=FBA_FEE_PREVIEW_TARGET_TABLE_SPEC.business_key_fields,
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
    "FBA_FEE_PREVIEW_EXPECTED_FIELDS",
    "FBA_FEE_PREVIEW_REQUIRED_FIELDS",
    "FBA_FEE_PREVIEW_TARGET_TABLE",
    "FBA_FEE_PREVIEW_TARGET_TABLE_SPEC",
    "FbaFeePreviewTargetTableSpec",
    "compute_business_key_hash",
    "compute_fba_fee_preview_business_key_hash",
    "map_fba_fee_preview_record_to_table_row",
    "read_jsonl",
    "write_jsonl",
]
