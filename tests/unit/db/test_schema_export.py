from __future__ import annotations

from seller_data_pipeline.db.schema_export import (
    normalise_schema_snapshot,
    render_schema_markdown,
    sql_type_label,
)


def test_sql_type_label_formats_common_sql_server_types() -> None:
    assert sql_type_label({"data_type": "nvarchar", "max_length": 100}) == "NVARCHAR(100)"
    assert sql_type_label({"data_type": "nvarchar", "max_length": -1}) == "NVARCHAR(MAX)"
    assert sql_type_label({"data_type": "decimal", "precision": 18, "scale": 4}) == "DECIMAL(18,4)"
    assert sql_type_label({"data_type": "datetime2", "scale": 7}) == "DATETIME2(7)"
    assert sql_type_label({"data_type": "bigint"}) == "BIGINT"


def test_normalise_schema_snapshot_groups_columns_indexes_constraints_and_foreign_keys() -> None:
    raw_snapshot = {
        "generated_at_utc": "2026-05-16T00:00:00+00:00",
        "database": {"database_name": "amazon_ops"},
        "tables": [
            {
                "schema_name": "dbo",
                "table_name": "parent_table",
                "object_id": 1,
                "create_date": "2026-01-01T00:00:00",
                "modify_date": "2026-01-01T00:00:00",
            },
            {
                "schema_name": "dbo",
                "table_name": "child_table",
                "object_id": 2,
                "create_date": "2026-01-01T00:00:00",
                "modify_date": "2026-01-01T00:00:00",
            },
        ],
        "columns": [
            {
                "schema_name": "dbo",
                "table_name": "child_table",
                "column_id": 1,
                "column_name": "id",
                "data_type": "bigint",
                "max_length": 8,
                "precision": 19,
                "scale": 0,
                "is_nullable": False,
                "is_identity": True,
                "identity_seed": "1",
                "identity_increment": "1",
                "default_definition": None,
            },
            {
                "schema_name": "dbo",
                "table_name": "child_table",
                "column_id": 2,
                "column_name": "parent_id",
                "data_type": "bigint",
                "max_length": 8,
                "precision": 19,
                "scale": 0,
                "is_nullable": False,
                "is_identity": False,
                "identity_seed": None,
                "identity_increment": None,
                "default_definition": None,
            },
        ],
        "index_columns": [
            {
                "schema_name": "dbo",
                "table_name": "child_table",
                "index_name": "IX_child_parent",
                "type_desc": "NONCLUSTERED",
                "is_unique": False,
                "is_primary_key": False,
                "is_unique_constraint": False,
                "has_filter": False,
                "filter_definition": None,
                "key_ordinal": 1,
                "index_column_id": 1,
                "is_included_column": False,
                "is_descending_key": False,
                "column_name": "parent_id",
            }
        ],
        "key_constraints": [
            {
                "schema_name": "dbo",
                "table_name": "child_table",
                "constraint_name": "PK_child_table",
                "constraint_type": "PK",
                "constraint_type_desc": "PRIMARY_KEY_CONSTRAINT",
                "backing_index_name": "PK_child_table",
            }
        ],
        "foreign_key_columns": [
            {
                "foreign_key_name": "FK_child_parent",
                "parent_schema_name": "dbo",
                "parent_table_name": "child_table",
                "parent_column_name": "parent_id",
                "referenced_schema_name": "dbo",
                "referenced_table_name": "parent_table",
                "referenced_column_name": "id",
                "constraint_column_id": 1,
                "delete_referential_action_desc": "NO_ACTION",
                "update_referential_action_desc": "NO_ACTION",
                "is_disabled": False,
                "is_not_trusted": False,
            }
        ],
        "row_counts": [
            {"schema_name": "dbo", "table_name": "child_table", "row_count": 3},
        ],
    }

    snapshot = normalise_schema_snapshot(raw_snapshot)

    assert snapshot["table_count"] == 2
    child_table = next(
        table for table in snapshot["tables"] if table["table_name"] == "child_table"
    )
    assert child_table["row_count"] == 3
    assert [column["column_name"] for column in child_table["columns"]] == ["id", "parent_id"]
    assert child_table["indexes"][0]["index_name"] == "IX_child_parent"
    assert child_table["key_constraints"][0]["constraint_name"] == "PK_child_table"
    assert child_table["foreign_keys"][0]["foreign_key_name"] == "FK_child_parent"


def test_render_schema_markdown_contains_live_schema_warning_and_table_details() -> None:
    snapshot = {
        "generated_at_utc": "2026-05-16T00:00:00+00:00",
        "database": {
            "database_name": "amazon_ops",
            "server_name": "amazon-ops-sql",
            "edition": "SQL Azure",
            "login_name": "sqladminuser",
        },
        "table_count": 1,
        "tables": [
            {
                "schema_name": "dbo",
                "table_name": "amazon_listing_snapshot",
                "create_date": "2026-05-16T00:00:00",
                "modify_date": "2026-05-16T00:00:00",
                "row_count": 6,
                "columns": [
                    {
                        "column_id": 1,
                        "column_name": "business_key_hash",
                        "data_type": "nvarchar",
                        "max_length": 100,
                        "precision": 0,
                        "scale": 0,
                        "is_nullable": True,
                        "is_identity": False,
                        "default_definition": None,
                    }
                ],
                "indexes": [
                    {
                        "index_name": "UX_amazon_listing_snapshot_business_key_hash",
                        "type_desc": "NONCLUSTERED",
                        "is_unique": True,
                        "filter_definition": "([business_key_hash] IS NOT NULL)",
                        "key_columns": [
                            {
                                "column_name": "business_key_hash",
                                "is_descending_key": False,
                            }
                        ],
                        "included_columns": [],
                    }
                ],
                "key_constraints": [],
                "foreign_keys": [],
            }
        ],
    }

    markdown = render_schema_markdown(snapshot)

    assert "# Azure SQL Live Schema Export" in markdown
    assert "not a replacement for the curated spec" in markdown
    assert "`dbo.amazon_listing_snapshot`" in markdown
    assert "`business_key_hash`" in markdown
    assert "`NVARCHAR(100)`" in markdown
    assert "`UX_amazon_listing_snapshot_business_key_hash`" in markdown


def test_columns_sql_casts_identity_sql_variant_values_for_pyodbc() -> None:
    from seller_data_pipeline.db.schema_export import COLUMNS_SQL

    assert "CONVERT(nvarchar(100), ic.seed_value) AS identity_seed" in COLUMNS_SQL
    assert "CONVERT(nvarchar(100), ic.increment_value) AS identity_increment" in COLUMNS_SQL
    assert "    ic.seed_value AS identity_seed," not in COLUMNS_SQL
    assert "    ic.increment_value AS identity_increment," not in COLUMNS_SQL


class _FailingCursor:
    description = [("value",)]

    def __init__(self) -> None:
        self.closed = False

    def execute(self, sql: str) -> None:
        raise RuntimeError("ODBC SQL type -150 is not yet supported")

    def close(self) -> None:
        self.closed = True


class _FailingConnection:
    def __init__(self) -> None:
        self.cursor_instance = _FailingCursor()

    def cursor(self) -> _FailingCursor:
        return self.cursor_instance


def test_execute_query_wraps_catalog_driver_errors_with_context() -> None:
    import pytest

    from seller_data_pipeline.common.exceptions import AzureSqlSchemaExportError
    from seller_data_pipeline.db.schema_export import execute_query

    connection = _FailingConnection()

    with pytest.raises(AzureSqlSchemaExportError) as exc_info:
        execute_query(connection, "SELECT 1", query_name="columns catalog")

    assert "columns catalog" in str(exc_info.value)
    assert "ODBC SQL type" in str(exc_info.value)
    assert connection.cursor_instance.closed is True
