import pytest

from seller_data_pipeline.db.repositories.promotion_coupon_repo import (
    build_promotion_coupon_merge_sql,
    validate_promotion_coupon_table_spec,
)
from seller_data_pipeline.ingestion.promotion_coupon_table_mapping import (
    PROMOTION_PERFORMANCE_TARGET_TABLE_SPEC,
    PromotionCouponTargetTableSpec,
)


def test_build_merge_sql_uses_business_key_hash() -> None:
    sql = build_promotion_coupon_merge_sql(
        table_spec=PROMOTION_PERFORMANCE_TARGET_TABLE_SPEC,
    )
    assert "MERGE dbo.[amazon_promotion_performance]" in sql
    assert "business_key_hash" in sql
    assert "OUTPUT $action" in sql


def test_validate_table_spec_rejects_unallowlisted_table() -> None:
    bad_spec = PromotionCouponTargetTableSpec(
        report_type="GET_PROMOTION_PERFORMANCE_REPORT",
        target_table="unsafe_table",
        business_key_fields=("id",),
        table_columns=("source_row_index", "business_key_hash"),
        expected_fields=(),
        required_fields=(),
    )
    with pytest.raises(ValueError):
        validate_promotion_coupon_table_spec(bad_spec)
