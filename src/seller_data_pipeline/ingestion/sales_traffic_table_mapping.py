from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from seller_data_pipeline.parsers.amazon.sales_report_parser import (
    SALES_AND_TRAFFIC_REPORT_TYPE,
    SalesAndTrafficAsinRecord,
    SalesAndTrafficDateRecord,
)
from seller_data_pipeline.sampling.report_analyzer import SALES_AND_TRAFFIC_MAPPED_FIELDS

SALES_TRAFFIC_DAILY_TARGET_TABLE = "amazon_sales_traffic_daily"
SALES_TRAFFIC_ASIN_TARGET_TABLE = "amazon_sales_traffic_asin_daily"

SALES_TRAFFIC_EXPECTED_FIELDS: tuple[str, ...] = tuple(sorted(SALES_AND_TRAFFIC_MAPPED_FIELDS))
SALES_TRAFFIC_REQUIRED_FIELDS: tuple[str, ...] = SALES_TRAFFIC_EXPECTED_FIELDS


@dataclass(frozen=True)
class SalesTrafficTargetTableSpec:
    """Target-table mapping contract for GET_SALES_AND_TRAFFIC_REPORT.

    Keep this contract aligned with docs/features/feature_sales_traffic_ingestion.md,
    docs/database/database_current_schema_spec.md and sql/migrations/005_*.
    """

    report_type: str
    target_table: str
    business_key_fields: tuple[str, ...]
    table_columns: tuple[str, ...]
    expected_fields: tuple[str, ...]
    required_fields: tuple[str, ...]


SALES_TRAFFIC_DAILY_TABLE_SPEC = SalesTrafficTargetTableSpec(
    report_type=SALES_AND_TRAFFIC_REPORT_TYPE,
    target_table=SALES_TRAFFIC_DAILY_TARGET_TABLE,
    business_key_fields=("marketplace_id", "report_date", "date_granularity"),
    table_columns=(
        "marketplace_id",
        "report_date",
        "date_granularity",
        "asin_granularity",
        "ordered_product_sales_amount",
        "ordered_product_sales_currency",
        "ordered_product_sales_b2b_amount",
        "ordered_product_sales_b2b_currency",
        "average_sales_per_order_item_amount",
        "average_sales_per_order_item_currency",
        "average_sales_per_order_item_b2b_amount",
        "average_sales_per_order_item_b2b_currency",
        "average_units_per_order_item",
        "average_units_per_order_item_b2b",
        "average_selling_price_amount",
        "average_selling_price_currency",
        "average_selling_price_b2b_amount",
        "average_selling_price_b2b_currency",
        "units_ordered",
        "units_ordered_b2b",
        "total_order_items",
        "total_order_items_b2b",
        "units_refunded",
        "refund_rate",
        "claims_granted",
        "claims_amount",
        "claims_amount_currency",
        "shipped_product_sales_amount",
        "shipped_product_sales_currency",
        "units_shipped",
        "orders_shipped",
        "browser_page_views",
        "mobile_app_page_views",
        "page_views",
        "browser_sessions",
        "mobile_app_sessions",
        "sessions",
        "buy_box_percentage",
        "order_item_session_percentage",
        "unit_session_percentage",
        "average_offer_count",
        "average_parent_items",
        "feedback_received",
        "negative_feedback_received",
        "received_negative_feedback_rate",
        "source_system",
        "source_report_type",
        "source_report_id",
        "source_report_request_id",
        "source_raw_file_id",
        "source_raw_file_path",
        "source_run_id",
        "source_row_hash",
        "raw_data",
        "business_key_hash",
    ),
    expected_fields=SALES_TRAFFIC_EXPECTED_FIELDS,
    required_fields=SALES_TRAFFIC_REQUIRED_FIELDS,
)

SALES_TRAFFIC_ASIN_TABLE_SPEC = SalesTrafficTargetTableSpec(
    report_type=SALES_AND_TRAFFIC_REPORT_TYPE,
    target_table=SALES_TRAFFIC_ASIN_TARGET_TABLE,
    business_key_fields=(
        "marketplace_id",
        "report_start_date",
        "report_end_date",
        "asin_granularity",
        "parent_asin",
        "child_asin",
    ),
    table_columns=(
        "marketplace_id",
        "report_start_date",
        "report_end_date",
        "parent_asin",
        "child_asin",
        "date_granularity",
        "asin_granularity",
        "ordered_product_sales_amount",
        "ordered_product_sales_currency",
        "ordered_product_sales_b2b_amount",
        "ordered_product_sales_b2b_currency",
        "units_ordered",
        "units_ordered_b2b",
        "total_order_items",
        "total_order_items_b2b",
        "browser_page_views",
        "browser_page_views_b2b",
        "browser_page_views_percentage",
        "browser_page_views_percentage_b2b",
        "mobile_app_page_views",
        "mobile_app_page_views_b2b",
        "mobile_app_page_views_percentage",
        "mobile_app_page_views_percentage_b2b",
        "page_views",
        "page_views_b2b",
        "page_views_percentage",
        "page_views_percentage_b2b",
        "browser_sessions",
        "browser_sessions_b2b",
        "browser_session_percentage",
        "browser_session_percentage_b2b",
        "mobile_app_sessions",
        "mobile_app_sessions_b2b",
        "mobile_app_session_percentage",
        "mobile_app_session_percentage_b2b",
        "sessions",
        "sessions_b2b",
        "session_percentage",
        "session_percentage_b2b",
        "buy_box_percentage",
        "buy_box_percentage_b2b",
        "unit_session_percentage",
        "unit_session_percentage_b2b",
        "source_system",
        "source_report_type",
        "source_report_id",
        "source_report_request_id",
        "source_raw_file_id",
        "source_raw_file_path",
        "source_run_id",
        "source_row_hash",
        "raw_data",
        "business_key_hash",
    ),
    expected_fields=SALES_TRAFFIC_EXPECTED_FIELDS,
    required_fields=SALES_TRAFFIC_REQUIRED_FIELDS,
)

SALES_TRAFFIC_TARGET_TABLE_SPECS: tuple[SalesTrafficTargetTableSpec, ...] = (
    SALES_TRAFFIC_DAILY_TABLE_SPEC,
    SALES_TRAFFIC_ASIN_TABLE_SPEC,
)


def map_sales_traffic_date_record_to_table_row(
    record: SalesAndTrafficDateRecord,
) -> dict[str, Any]:
    base_row = record.to_dict()
    base_row["source_report_request_id"] = None
    base_row["source_raw_file_id"] = None
    base_row["source_run_id"] = None
    base_row["business_key_hash"] = compute_sales_traffic_business_key_hash(
        row=base_row,
        table_spec=SALES_TRAFFIC_DAILY_TABLE_SPEC,
    )
    base_row["raw_data"] = _json_dumps(base_row.get("raw_data", {}))
    return {
        column: _json_ready(base_row.get(column))
        for column in SALES_TRAFFIC_DAILY_TABLE_SPEC.table_columns
    }


def map_sales_traffic_asin_record_to_table_row(
    record: SalesAndTrafficAsinRecord,
) -> dict[str, Any]:
    base_row = record.to_dict()
    base_row["source_report_request_id"] = None
    base_row["source_raw_file_id"] = None
    base_row["source_run_id"] = None
    base_row["business_key_hash"] = compute_sales_traffic_business_key_hash(
        row=base_row,
        table_spec=SALES_TRAFFIC_ASIN_TABLE_SPEC,
    )
    base_row["raw_data"] = _json_dumps(base_row.get("raw_data", {}))
    return {
        column: _json_ready(base_row.get(column))
        for column in SALES_TRAFFIC_ASIN_TABLE_SPEC.table_columns
    }


def compute_sales_traffic_business_key_hash(
    *,
    row: dict[str, Any],
    table_spec: SalesTrafficTargetTableSpec,
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
    "SALES_AND_TRAFFIC_REPORT_TYPE",
    "SALES_TRAFFIC_ASIN_TABLE_SPEC",
    "SALES_TRAFFIC_ASIN_TARGET_TABLE",
    "SALES_TRAFFIC_DAILY_TABLE_SPEC",
    "SALES_TRAFFIC_DAILY_TARGET_TABLE",
    "SALES_TRAFFIC_EXPECTED_FIELDS",
    "SALES_TRAFFIC_REQUIRED_FIELDS",
    "SALES_TRAFFIC_TARGET_TABLE_SPECS",
    "SalesTrafficTargetTableSpec",
    "compute_business_key_hash",
    "compute_sales_traffic_business_key_hash",
    "map_sales_traffic_asin_record_to_table_row",
    "map_sales_traffic_date_record_to_table_row",
    "read_jsonl",
    "write_jsonl",
]
