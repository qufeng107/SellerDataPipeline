from seller_data_pipeline.ingestion.promotion_coupon_table_mapping import (
    COUPON_ASIN_TARGET_TABLE_SPEC,
    COUPON_PERFORMANCE_TARGET_TABLE_SPEC,
    PROMOTION_PERFORMANCE_TARGET_TABLE_SPEC,
    PROMOTION_PRODUCT_TARGET_TABLE_SPEC,
    compute_business_key_hash,
)


def test_promotion_coupon_specs_have_required_upsert_columns() -> None:
    for spec in (
        PROMOTION_PERFORMANCE_TARGET_TABLE_SPEC,
        PROMOTION_PRODUCT_TARGET_TABLE_SPEC,
        COUPON_PERFORMANCE_TARGET_TABLE_SPEC,
        COUPON_ASIN_TARGET_TABLE_SPEC,
    ):
        assert "source_row_index" in spec.table_columns
        assert "business_key_hash" in spec.table_columns
        assert spec.business_key_fields


def test_business_key_hash_is_stable_and_table_scoped() -> None:
    row = {"marketplace_id": "ATVPDKIKX0DER", "promotion_id": "p1"}
    first = compute_business_key_hash(
        target_table="amazon_promotion_performance",
        business_key_fields=("marketplace_id", "promotion_id"),
        row=row,
    )
    second = compute_business_key_hash(
        target_table="amazon_promotion_performance",
        business_key_fields=("marketplace_id", "promotion_id"),
        row=dict(reversed(row.items())),
    )
    different_table = compute_business_key_hash(
        target_table="amazon_promotion_product_performance",
        business_key_fields=("marketplace_id", "promotion_id"),
        row=row,
    )
    assert first == second
    assert first != different_table
