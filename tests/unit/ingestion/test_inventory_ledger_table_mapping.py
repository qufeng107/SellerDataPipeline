from seller_data_pipeline.ingestion.inventory_ledger_table_mapping import (
    LEDGER_DETAIL_TARGET_TABLE_SPEC,
    LEDGER_SUMMARY_TARGET_TABLE_SPEC,
    compute_business_key_hash,
)


def test_inventory_ledger_specs_have_required_upsert_columns() -> None:
    for spec in (LEDGER_SUMMARY_TARGET_TABLE_SPEC, LEDGER_DETAIL_TARGET_TABLE_SPEC):
        assert "source_row_index" in spec.table_columns
        assert "business_key_hash" in spec.table_columns
        assert spec.business_key_fields


def test_business_key_hash_is_stable_and_table_scoped() -> None:
    row = {"marketplace_id": "ATVPDKIKX0DER", "seller_sku": "SKU-1", "source_row_index": 1}
    first = compute_business_key_hash(
        target_table="amazon_inventory_ledger_detail",
        business_key_fields=("marketplace_id", "seller_sku", "source_row_index"),
        row=row,
    )
    second = compute_business_key_hash(
        target_table="amazon_inventory_ledger_detail",
        business_key_fields=("marketplace_id", "seller_sku", "source_row_index"),
        row=dict(reversed(row.items())),
    )
    different_table = compute_business_key_hash(
        target_table="amazon_inventory_ledger_summary_daily",
        business_key_fields=("marketplace_id", "seller_sku", "source_row_index"),
        row=row,
    )
    assert first == second
    assert first != different_table
