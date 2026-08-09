from seller_data_pipeline.db.settlement_sql import settlement_date_sql


def test_settlement_date_sql_uses_explicit_iso_and_dot_formats_only() -> None:
    sql = settlement_date_sql(
        "[posted_date_time_raw]",
        "[posted_date_raw]",
        "[deposit_date_raw]",
    )

    assert "TRY_CONVERT(date" in sql
    assert ", 23)" in sql
    assert ", 104)" in sql
    assert ", 112)" in sql
    assert "TRY_CONVERT(date, NULLIF([posted_date_raw], ''))" not in sql
