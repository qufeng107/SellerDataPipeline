from __future__ import annotations

from seller_data_pipeline.db.repositories.settlement_repo import (
    SettlementRepo,
    build_insert_sql,
    build_settlement_merge_sql,
)
from seller_data_pipeline.ingestion.settlement_table_mapping import SETTLEMENT_TARGET_TABLE_SPEC


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


def test_build_settlement_merge_sql_uses_business_key_hash() -> None:
    sql = build_settlement_merge_sql(table_spec=SETTLEMENT_TARGET_TABLE_SPEC)

    assert "MERGE dbo.[amazon_settlement_transaction]" in sql
    assert "ON target.[business_key_hash] = source.[business_key_hash]" in sql
    assert "OUTPUT $action AS merge_action" in sql
    assert "target.[updated_at] = SYSUTCDATETIME()" in sql


def test_settlement_insert_sql_rejects_unknown_table() -> None:
    try:
        build_insert_sql(table_name="not_allowed", columns=("id",))
    except ValueError as exc:
        assert "not allowlisted" in str(exc)
    else:  # pragma: no cover - defensive test branch
        raise AssertionError("Expected ValueError")


def test_settlement_repo_upsert_counts_merge_actions() -> None:
    cursor = FakeCursor(fetch_values=[["INSERT"], ["UPDATE"]])
    repo = SettlementRepo(FakeConnection(cursor))
    row = {column: None for column in SETTLEMENT_TARGET_TABLE_SPEC.table_columns}
    row.update(
        {
            "marketplace_id": "ATVPDKIKX0DER",
            "source_report_type": "GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2",
            "source_report_id": "settlement-report-1",
            "source_raw_file_path": "reports/raw/settlement-report-1.txt",
            "source_row_index": 1,
            "source_row_hash": "source-hash-1",
            "business_key_hash": "business-hash-1",
            "amount_category": "product_sales",
            "profit_bucket": "revenue",
            "source_system": "sp_api_reports",
            "raw_data": "{}",
        }
    )
    row2 = dict(row)
    row2["source_row_index"] = 2
    row2["business_key_hash"] = "business-hash-2"

    result = repo.upsert_settlement_transaction_rows(rows=[row, row2], source_run_id=42)

    assert result.attempted_rows == 2
    assert result.inserted_rows == 1
    assert result.updated_rows == 1
    assert len(cursor.executed) == 2
    assert cursor.executed[0][1][SETTLEMENT_TARGET_TABLE_SPEC.table_columns.index("source_run_id")] == 42


def test_settlement_repo_insert_and_update_sync_run_log() -> None:
    cursor = FakeCursor(fetch_values=[[123]])
    repo = SettlementRepo(FakeConnection(cursor))
    event = {
        "workflow_name": "sp_api_settlement_ingestion",
        "job_name": "ingest_settlement_report",
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
