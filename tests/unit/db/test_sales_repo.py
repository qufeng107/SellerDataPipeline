from __future__ import annotations

from seller_data_pipeline.db.repositories.sales_repo import (
    SalesRepo,
    build_insert_sql,
    build_sales_traffic_merge_sql,
)
from seller_data_pipeline.ingestion.sales_traffic_table_mapping import (
    SALES_TRAFFIC_ASIN_TABLE_SPEC,
    SALES_TRAFFIC_DAILY_TABLE_SPEC,
)


class FakeCursor:
    def __init__(self, fetch_values: list[object] | None = None) -> None:
        self.executed: list[tuple[str, tuple[object, ...]]] = []
        self.fetch_values = fetch_values or []

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        self.executed.append((sql, params))

    def fetchone(self) -> object:
        return self.fetch_values.pop(0) if self.fetch_values else ["UPDATE"]


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.committed = False

    def cursor(self) -> FakeCursor:
        return self._cursor

    def commit(self) -> None:
        self.committed = True


def test_build_sales_traffic_merge_sql_uses_business_key_hash() -> None:
    sql = build_sales_traffic_merge_sql(table_spec=SALES_TRAFFIC_DAILY_TABLE_SPEC)

    assert "MERGE dbo.[amazon_sales_traffic_daily]" in sql
    assert "ON target.[business_key_hash] = source.[business_key_hash]" in sql
    assert "OUTPUT $action AS merge_action" in sql
    assert "target.[updated_at] = SYSUTCDATETIME()" in sql


def test_sales_insert_sql_rejects_unknown_table() -> None:
    try:
        build_insert_sql(table_name="not_allowed", columns=("id",))
    except ValueError as exc:
        assert "not allowlisted" in str(exc)
    else:  # pragma: no cover - defensive test branch
        raise AssertionError("Expected ValueError")


def test_sales_repo_upsert_counts_merge_actions_for_daily_and_asin() -> None:
    cursor = FakeCursor(fetch_values=[["INSERT"], ["UPDATE"], ["INSERT"]])
    repo = SalesRepo(FakeConnection(cursor))
    daily_row = {column: None for column in SALES_TRAFFIC_DAILY_TABLE_SPEC.table_columns}
    daily_row.update(
        {
            "marketplace_id": "ATVPDKIKX0DER",
            "report_date": "2026-05-14",
            "business_key_hash": "daily-hash-1",
            "source_row_hash": "source-hash-1",
            "source_system": "sp_api_reports",
            "source_report_type": "GET_SALES_AND_TRAFFIC_REPORT",
            "raw_data": "{}",
        }
    )
    daily_row2 = dict(daily_row)
    daily_row2["business_key_hash"] = "daily-hash-2"
    asin_row = {column: None for column in SALES_TRAFFIC_ASIN_TABLE_SPEC.table_columns}
    asin_row.update(
        {
            "marketplace_id": "ATVPDKIKX0DER",
            "report_start_date": "2026-05-07",
            "report_end_date": "2026-05-14",
            "parent_asin": "B000TEST01",
            "business_key_hash": "asin-hash-1",
            "source_row_hash": "source-hash-2",
            "source_system": "sp_api_reports",
            "source_report_type": "GET_SALES_AND_TRAFFIC_REPORT",
            "raw_data": "{}",
        }
    )

    daily_result = repo.upsert_sales_traffic_daily_rows(
        rows=[daily_row, daily_row2],
        source_run_id=42,
    )
    asin_result = repo.upsert_sales_traffic_asin_rows(rows=[asin_row], source_run_id=42)

    assert daily_result.attempted_rows == 2
    assert daily_result.inserted_rows == 1
    assert daily_result.updated_rows == 1
    assert asin_result.attempted_rows == 1
    assert asin_result.inserted_rows == 1
    assert len(cursor.executed) == 3
    assert cursor.executed[0][1][SALES_TRAFFIC_DAILY_TABLE_SPEC.table_columns.index("source_run_id")] == 42


def test_sales_repo_insert_and_update_sync_run_log() -> None:
    cursor = FakeCursor(fetch_values=[[123]])
    repo = SalesRepo(FakeConnection(cursor))
    event = {
        "workflow_name": "sp_api_sales_traffic_ingestion",
        "job_name": "ingest_sales_traffic_report",
        "task_type": "ingestion_upsert",
        "trigger_type": "manual",
        "run_mode": "azure_sql_write",
        "status": "running",
        "started_at": "2026-05-17T21:00:00Z",
    }

    run_id = repo.insert_sync_run_log(event)
    repo.update_sync_run_log(run_id, {**event, "status": "success"})

    assert run_id == 123
    assert len(cursor.executed) == 2
    assert "OUTPUT INSERTED.[id]" in cursor.executed[0][0]
    assert "UPDATE dbo.[amazon_sync_run_log]" in cursor.executed[1][0]
