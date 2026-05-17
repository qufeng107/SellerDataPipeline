from __future__ import annotations

from seller_data_pipeline.ingestion.sales_traffic_table_mapping import (
    SALES_TRAFFIC_ASIN_TABLE_SPEC,
    SALES_TRAFFIC_DAILY_TABLE_SPEC,
    compute_business_key_hash,
)


def test_sales_traffic_table_specs_include_business_key_hash() -> None:
    assert SALES_TRAFFIC_DAILY_TABLE_SPEC.target_table == "amazon_sales_traffic_daily"
    assert SALES_TRAFFIC_ASIN_TABLE_SPEC.target_table == "amazon_sales_traffic_asin_daily"
    assert "business_key_hash" in SALES_TRAFFIC_DAILY_TABLE_SPEC.table_columns
    assert "business_key_hash" in SALES_TRAFFIC_ASIN_TABLE_SPEC.table_columns
    assert SALES_TRAFFIC_DAILY_TABLE_SPEC.business_key_fields == (
        "marketplace_id",
        "report_date",
        "date_granularity",
    )
    assert SALES_TRAFFIC_ASIN_TABLE_SPEC.business_key_fields == (
        "marketplace_id",
        "report_start_date",
        "report_end_date",
        "asin_granularity",
        "parent_asin",
        "child_asin",
    )


def test_sales_traffic_business_key_hash_is_stable_and_table_scoped() -> None:
    row = {
        "marketplace_id": "ATVPDKIKX0DER",
        "report_date": "2026-05-14",
        "date_granularity": "DAY",
    }

    hash_1 = compute_business_key_hash(
        target_table=SALES_TRAFFIC_DAILY_TABLE_SPEC.target_table,
        business_key_fields=SALES_TRAFFIC_DAILY_TABLE_SPEC.business_key_fields,
        row=row,
    )
    hash_2 = compute_business_key_hash(
        target_table=SALES_TRAFFIC_DAILY_TABLE_SPEC.target_table,
        business_key_fields=SALES_TRAFFIC_DAILY_TABLE_SPEC.business_key_fields,
        row={**row, "units_ordered": 999},
    )
    hash_3 = compute_business_key_hash(
        target_table=SALES_TRAFFIC_ASIN_TABLE_SPEC.target_table,
        business_key_fields=("marketplace_id", "report_date", "date_granularity"),
        row=row,
    )

    assert hash_1 == hash_2
    assert hash_1 != hash_3
