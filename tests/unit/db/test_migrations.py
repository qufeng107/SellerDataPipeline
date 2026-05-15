from __future__ import annotations

from pathlib import Path

from seller_data_pipeline.db.migrations import read_sql_batches, split_tsql_batches


def test_split_tsql_batches_removes_go_separators() -> None:
    sql = """
    CREATE TABLE dbo.a (id int);
    GO
    CREATE TABLE dbo.b (id int);
    go -- lowercase is accepted
    """

    batches = split_tsql_batches(sql)

    assert batches == [
        "CREATE TABLE dbo.a (id int);",
        "CREATE TABLE dbo.b (id int);",
    ]


def test_split_tsql_batches_supports_go_repeat_count() -> None:
    sql = """
    INSERT INTO dbo.a VALUES (1);
    GO 2
    """

    batches = split_tsql_batches(sql)

    assert batches == ["INSERT INTO dbo.a VALUES (1);", "INSERT INTO dbo.a VALUES (1);"]


def test_read_sql_batches_handles_utf8_bom(tmp_path: Path) -> None:
    sql_file = tmp_path / "001.sql"
    sql_file.write_text("\ufeffSELECT 1;\nGO\nSELECT 2;\n", encoding="utf-8")

    batches = read_sql_batches(sql_file)

    assert batches == ["SELECT 1;", "SELECT 2;"]


def test_initial_migration_contains_confirmed_ads_core_tables() -> None:
    project_root = Path(__file__).resolve().parents[3]
    sql_text = (project_root / "sql/migrations/001_create_core_tables.sql").read_text(
        encoding="utf-8"
    )

    assert "dbo.amazon_ads_profile" in sql_text
    assert "dbo.amazon_ads_sp_campaign_daily" in sql_text
    assert "dbo.amazon_ads_sp_targeting_daily" in sql_text
    assert "dbo.amazon_ads_sp_search_term_daily" in sql_text
    assert "dbo.amazon_ads_sp_advertised_product_daily" in sql_text
    assert "dbo.amazon_ads_sp_purchased_product_daily" not in sql_text
    assert "business_key_hash NVARCHAR(100) NOT NULL" in sql_text


def test_ads_index_migration_contains_confirmed_ads_core_indexes() -> None:
    project_root = Path(__file__).resolve().parents[3]
    sql_text = (project_root / "sql/migrations/002_create_indexes.sql").read_text(
        encoding="utf-8"
    )

    assert "IX_amazon_ads_sp_campaign_daily_key" in sql_text
    assert "IX_amazon_ads_sp_targeting_daily_key" in sql_text
    assert "IX_amazon_ads_sp_search_term_daily_key" in sql_text
    assert "IX_amazon_ads_sp_advertised_product_daily_key" in sql_text
    assert "UX_amazon_ads_sp_campaign_daily_business_key" in sql_text
    assert "UX_amazon_ads_sp_targeting_daily_business_key" in sql_text
    assert "UX_amazon_ads_sp_search_term_daily_business_key" in sql_text
    assert "UX_amazon_ads_sp_advertised_product_daily_business_key" in sql_text

