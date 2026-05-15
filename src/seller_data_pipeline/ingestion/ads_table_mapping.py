from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from seller_data_pipeline.parsers.amazon.ads_report_parser import AdsReportRecord


@dataclass(frozen=True)
class AdsTargetTableSpec:
    """Target-table mapping contract for one Amazon Ads report type.

    This contract is intentionally independent from pyodbc/repository code so it can be tested and
    used in local dry-runs before the Azure SQL schema exists. The same fields should be mirrored in
    requirements/database_spec.md and sql/migrations before a real upsert repository is enabled.
    """

    report_type_id: str
    target_table: str
    business_key_fields: tuple[str, ...]
    table_columns: tuple[str, ...]
    allow_empty_report: bool = True
    table_ready: bool = True
    notes: str = ""


COMMON_SOURCE_COLUMNS = (
    "source_system",
    "source_report_type",
    "source_report_id",
    "source_report_request_id",
    "source_raw_file_id",
    "source_raw_file_path",
    "source_run_id",
    "source_row_index",
    "source_row_hash",
    "business_key_hash",
    "raw_data",
)

COMMON_METRIC_COLUMNS = (
    "impressions",
    "clicks",
    "cost",
    "sales_7d",
    "purchases_7d",
    "units_sold_clicks_7d",
)

ADS_TARGET_TABLE_SPECS: tuple[AdsTargetTableSpec, ...] = (
    AdsTargetTableSpec(
        report_type_id="spCampaigns",
        target_table="amazon_ads_sp_campaign_daily",
        business_key_fields=("profile_id", "report_date", "campaign_id"),
        table_columns=(
            "profile_id",
            "marketplace_id",
            "report_date",
            "campaign_id",
            "campaign_name",
            "campaign_status",
            *COMMON_METRIC_COLUMNS,
            *COMMON_SOURCE_COLUMNS,
        ),
        notes="Campaign-level daily Sponsored Products performance.",
    ),
    AdsTargetTableSpec(
        report_type_id="spTargeting",
        target_table="amazon_ads_sp_targeting_daily",
        business_key_fields=(
            "profile_id",
            "report_date",
            "campaign_id",
            "ad_group_id",
            "keyword_id",
            "targeting",
            "match_type",
        ),
        table_columns=(
            "profile_id",
            "marketplace_id",
            "report_date",
            "campaign_id",
            "campaign_name",
            "ad_group_id",
            "ad_group_name",
            "keyword_id",
            "keyword",
            "match_type",
            "targeting",
            *COMMON_METRIC_COLUMNS,
            *COMMON_SOURCE_COLUMNS,
        ),
        notes="Keyword/target-level daily Sponsored Products performance.",
    ),
    AdsTargetTableSpec(
        report_type_id="spSearchTerm",
        target_table="amazon_ads_sp_search_term_daily",
        business_key_fields=(
            "profile_id",
            "report_date",
            "campaign_id",
            "ad_group_id",
            "keyword_id",
            "targeting",
            "search_term",
            "match_type",
        ),
        table_columns=(
            "profile_id",
            "marketplace_id",
            "report_date",
            "campaign_id",
            "campaign_name",
            "ad_group_id",
            "ad_group_name",
            "keyword_id",
            "keyword",
            "match_type",
            "targeting",
            "search_term",
            *COMMON_METRIC_COLUMNS,
            *COMMON_SOURCE_COLUMNS,
        ),
        notes="Customer search-term daily Sponsored Products performance.",
    ),
    AdsTargetTableSpec(
        report_type_id="spAdvertisedProduct",
        target_table="amazon_ads_sp_advertised_product_daily",
        business_key_fields=(
            "profile_id",
            "report_date",
            "campaign_id",
            "ad_group_id",
            "advertised_asin",
            "advertised_sku",
        ),
        table_columns=(
            "profile_id",
            "marketplace_id",
            "report_date",
            "campaign_id",
            "campaign_name",
            "ad_group_id",
            "ad_group_name",
            "advertised_asin",
            "advertised_sku",
            *COMMON_METRIC_COLUMNS,
            *COMMON_SOURCE_COLUMNS,
        ),
        notes="Advertised SKU/ASIN daily Sponsored Products performance.",
    ),
    AdsTargetTableSpec(
        report_type_id="spPurchasedProduct",
        target_table="amazon_ads_sp_purchased_product_daily",
        business_key_fields=(
            "profile_id",
            "report_date",
            "campaign_id",
            "ad_group_id",
            "purchased_asin",
            "advertised_asin",
            "advertised_sku",
        ),
        table_columns=(
            "profile_id",
            "marketplace_id",
            "report_date",
            "campaign_id",
            "campaign_name",
            "ad_group_id",
            "ad_group_name",
            "purchased_asin",
            "advertised_asin",
            "advertised_sku",
            "sales_7d",
            "purchases_7d",
            "units_sold_clicks_7d",
            *COMMON_SOURCE_COLUMNS,
        ),
        table_ready=False,
        notes=(
            "API has been confirmed, but the first canary was empty; "
            "wait for a non-empty sample."
        ),
    ),
)


def get_ads_target_table_spec(report_type_id: str) -> AdsTargetTableSpec | None:
    for spec in ADS_TARGET_TABLE_SPECS:
        if spec.report_type_id == report_type_id:
            return spec
    return None


def map_ads_record_to_table_row(
    *,
    record: AdsReportRecord,
    table_spec: AdsTargetTableSpec,
    marketplace_id: str | None = None,
) -> dict[str, Any]:
    """Map one generic Ads parser record to a target-table row dict.

    The output uses database column names and JSON-serializable values. It is safe to write to
    preview JSONL files and later pass to repository/upsert code.
    """

    base_row = record.to_dict()
    base_row["marketplace_id"] = marketplace_id
    base_row["source_report_request_id"] = None
    base_row["source_raw_file_id"] = None
    base_row["source_run_id"] = None
    base_row["business_key_hash"] = compute_business_key_hash(
        target_table=table_spec.target_table,
        business_key_fields=table_spec.business_key_fields,
        row=base_row,
    )
    base_row["raw_data"] = _json_dumps(base_row.get("raw_data", {}))
    return {column: _json_ready(base_row.get(column)) for column in table_spec.table_columns}


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


def build_business_key_preview(
    *,
    table_spec: AdsTargetTableSpec,
    row: dict[str, Any],
) -> dict[str, Any]:
    return {field: row.get(field) for field in table_spec.business_key_fields}


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_json_dumps(row) + "\n")
    return output_path


def dataclass_to_json_dict(value: Any) -> dict[str, Any]:
    return json.loads(_json_dumps(asdict(value)))


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    input_path = Path(path)
    if not input_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with input_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def _json_dumps(value: Any) -> str:
    return json.dumps(
        _json_ready(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _json_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_ready(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    return value


__all__ = [
    "ADS_TARGET_TABLE_SPECS",
    "AdsTargetTableSpec",
    "build_business_key_preview",
    "compute_business_key_hash",
    "dataclass_to_json_dict",
    "get_ads_target_table_spec",
    "map_ads_record_to_table_row",
    "read_jsonl",
    "write_jsonl",
]
