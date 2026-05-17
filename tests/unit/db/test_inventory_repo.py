from __future__ import annotations

from seller_data_pipeline.db.repositories.inventory_repo import (
    InventoryRepo,
    build_insert_sql,
    build_inventory_merge_sql,
)
from seller_data_pipeline.ingestion.inventory_table_mapping import INVENTORY_TARGET_TABLE_SPEC


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


def test_build_inventory_merge_sql_uses_business_key_hash() -> None:
    sql = build_inventory_merge_sql(table_spec=INVENTORY_TARGET_TABLE_SPEC)

    assert "MERGE dbo.[amazon_inventory_daily]" in sql
    assert "ON target.[business_key_hash] = source.[business_key_hash]" in sql
    assert "OUTPUT $action AS merge_action" in sql
    assert "target.[updated_at] = SYSUTCDATETIME()" in sql


def test_inventory_insert_sql_rejects_unknown_table() -> None:
    try:
        build_insert_sql(table_name="not_allowed", columns=("id",))
    except ValueError as exc:
        assert "not allowlisted" in str(exc)
    else:  # pragma: no cover - defensive test branch
        raise AssertionError("Expected ValueError")


def test_inventory_repo_upsert_counts_merge_actions() -> None:
    cursor = FakeCursor(fetch_values=[["INSERT"], ["UPDATE"]])
    repo = InventoryRepo(FakeConnection(cursor))
    row = {column: None for column in INVENTORY_TARGET_TABLE_SPEC.table_columns}
    row.update(
        {
            "marketplace_id": "ATVPDKIKX0DER",
            "snapshot_date": "2026-05-14",
            "seller_sku": "SKU-1",
            "business_key_hash": "hash-1",
            "source_row_hash": "source-hash-1",
            "source_system": "sp_api_reports",
            "source_report_type": "GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA",
            "raw_data": "{}",
        }
    )
    row2 = dict(row)
    row2["business_key_hash"] = "hash-2"

    result = repo.upsert_inventory_rows(rows=[row, row2], source_run_id=42)

    assert result.attempted_rows == 2
    assert result.inserted_rows == 1
    assert result.updated_rows == 1
    assert result.written_rows == 2
    assert len(cursor.executed) == 2
    assert (
        cursor.executed[0][1][INVENTORY_TARGET_TABLE_SPEC.table_columns.index("source_run_id")]
        == 42
    )


def test_inventory_repo_insert_and_update_sync_run_log() -> None:
    cursor = FakeCursor(fetch_values=[[123]])
    repo = InventoryRepo(FakeConnection(cursor))
    event = {
        "workflow_name": "sp_api_inventory_ingestion",
        "job_name": "ingest_inventory_snapshot",
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
