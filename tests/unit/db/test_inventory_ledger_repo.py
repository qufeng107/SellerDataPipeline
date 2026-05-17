import pytest

from seller_data_pipeline.db.repositories.inventory_ledger_repo import (
    build_inventory_ledger_merge_sql,
    validate_inventory_ledger_table_spec,
)
from seller_data_pipeline.ingestion.inventory_ledger_table_mapping import (
    InventoryLedgerTargetTableSpec,
    LEDGER_SUMMARY_TARGET_TABLE_SPEC,
)


def test_build_merge_sql_uses_business_key_hash() -> None:
    sql = build_inventory_ledger_merge_sql(
        table_spec=LEDGER_SUMMARY_TARGET_TABLE_SPEC,
    )
    assert "MERGE dbo.[amazon_inventory_ledger_summary_daily]" in sql
    assert "business_key_hash" in sql
    assert "OUTPUT $action" in sql


def test_validate_table_spec_rejects_unallowlisted_table() -> None:
    bad_spec = InventoryLedgerTargetTableSpec(
        report_type="GET_LEDGER_SUMMARY_VIEW_DATA",
        target_table="unsafe_table",
        business_key_fields=("id",),
        table_columns=("source_row_index", "business_key_hash"),
        expected_fields=(),
        required_fields=(),
    )
    with pytest.raises(ValueError):
        validate_inventory_ledger_table_spec(bad_spec)
