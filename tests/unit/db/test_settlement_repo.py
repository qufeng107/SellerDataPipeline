from __future__ import annotations

import json

from seller_data_pipeline.db.repositories.settlement_repo import (
    SettlementRepo,
    build_insert_sql,
    build_settlement_json_merge_sql,
    collapse_settlement_payloads_by_business_key,
    build_settlement_merge_sql,
)
from seller_data_pipeline.ingestion.settlement_table_mapping import SETTLEMENT_TARGET_TABLE_SPEC


class FakeCursor:
    def __init__(
        self,
        fetch_values: list[object] | None = None,
        fetchall_values: list[object] | None = None,
    ) -> None:
        self.executed: list[tuple[str, tuple[object, ...]]] = []
        self.fetch_values = fetch_values or []
        self.fetchall_values = fetchall_values or []

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        self.executed.append((sql, params))

    def fetchone(self) -> object:
        return self.fetch_values.pop(0) if self.fetch_values else ["UPDATE"]

    def fetchall(self) -> list[object]:
        if self.fetchall_values:
            values = list(self.fetchall_values)
            self.fetchall_values.clear()
            return values
        if self.executed:
            sql, params = self.executed[-1]
            if "OPENJSON" in sql and params:
                payload = json.loads(str(params[0]))
                return [["UPDATE"] for _ in payload]
        return []


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.committed = False

    def cursor(self) -> FakeCursor:
        return self._cursor

    def commit(self) -> None:
        self.committed = True


def test_build_settlement_merge_sql_uses_immutable_business_key_only() -> None:
    sql = build_settlement_merge_sql(table_spec=SETTLEMENT_TARGET_TABLE_SPEC)

    assert "MERGE dbo.[amazon_settlement_transaction]" in sql
    on_sql = sql.split("WHEN MATCHED THEN", 1)[0]
    assert "ON target.[business_key_hash] = source.[business_key_hash]" in on_sql
    assert " OR (" not in on_sql
    assert "target.[marketplace_id] = source.[marketplace_id]" not in on_sql
    update_sql = sql.split("WHEN MATCHED THEN", 1)[1].split("WHEN NOT MATCHED THEN", 1)[0]
    assert "target.[business_key_hash] = source.[business_key_hash]" not in update_sql
    assert "OUTPUT $action AS merge_action" in sql
    assert "target.[updated_at] = SYSUTCDATETIME()" in sql


def test_settlement_insert_sql_rejects_unknown_table() -> None:
    try:
        build_insert_sql(table_name="not_allowed", columns=("id",))
    except ValueError as exc:
        assert "not allowlisted" in str(exc)
    else:  # pragma: no cover - defensive test branch
        raise AssertionError("Expected ValueError")


def _settlement_row(*, row_index: int, business_key_hash: str) -> dict[str, object]:
    row = {column: None for column in SETTLEMENT_TARGET_TABLE_SPEC.table_columns}
    row.update(
        {
            "marketplace_id": "ATVPDKIKX0DER",
            "source_report_type": "GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2",
            "source_report_id": "settlement-report-1",
            "source_raw_file_path": "reports/raw/settlement-report-1.txt",
            "source_row_index": row_index,
            "source_row_hash": f"source-hash-{row_index}",
            "business_key_hash": business_key_hash,
            "amount_category": "product_sales",
            "profit_bucket": "revenue",
            "source_system": "sp_api_reports",
            "raw_data": "{}",
        }
    )
    return row


def test_settlement_repo_upsert_counts_json_merge_actions() -> None:
    cursor = FakeCursor(fetchall_values=[["INSERT"], ["UPDATE"]])
    repo = SettlementRepo(FakeConnection(cursor))
    row = _settlement_row(row_index=1, business_key_hash="business-hash-1")
    row2 = _settlement_row(row_index=2, business_key_hash="business-hash-2")

    result = repo.upsert_settlement_transaction_rows(rows=[row, row2], source_run_id=42)

    assert result.attempted_rows == 2
    assert result.inserted_rows == 1
    assert result.updated_rows == 1
    assert len(cursor.executed) == 1
    sql, params = cursor.executed[0]
    assert "OPENJSON(CAST(? AS NVARCHAR(MAX)))" in sql
    assert len(params) == 1
    payload = json.loads(str(params[0]))
    assert len(payload) == 2
    assert payload[0]["source_run_id"] == 42


def test_settlement_json_merge_uses_immutable_business_key_only() -> None:
    sql = build_settlement_json_merge_sql(table_spec=SETTLEMENT_TARGET_TABLE_SPEC)

    assert "MERGE dbo.[amazon_settlement_transaction]" in sql
    assert "OPENJSON(CAST(? AS NVARCHAR(MAX)))" in sql
    assert "[raw_data] NVARCHAR(MAX) '$.raw_data'" in sql
    on_sql = sql.split("WHEN MATCHED THEN", 1)[0]
    assert "ON target.[business_key_hash] = source.[business_key_hash]" in on_sql
    update_sql = sql.split("WHEN MATCHED THEN", 1)[1].split("WHEN NOT MATCHED THEN", 1)[0]
    assert "target.[business_key_hash] = source.[business_key_hash]" not in update_sql
    assert "OUTPUT $action AS merge_action" in sql


def test_settlement_repo_batches_json_merge_without_parameter_explosion() -> None:
    row_count = 1201
    cursor = FakeCursor()
    repo = SettlementRepo(FakeConnection(cursor))
    rows = [
        _settlement_row(row_index=index, business_key_hash=f"business-hash-{index}")
        for index in range(1, row_count + 1)
    ]

    result = repo.upsert_settlement_transaction_rows(rows=rows, source_run_id=42)

    assert result.updated_rows == row_count
    assert len(cursor.executed) == 3
    assert all("OPENJSON" in sql for sql, _ in cursor.executed)
    assert all(len(params) == 1 for _, params in cursor.executed)
    assert [len(json.loads(str(params[0]))) for _, params in cursor.executed] == [500, 500, 201]


def test_settlement_repo_exact_duplicate_business_keys_collapse_last_write() -> None:
    cursor = FakeCursor(fetchall_values=[["INSERT"]])
    repo = SettlementRepo(FakeConnection(cursor))
    first = _settlement_row(row_index=1, business_key_hash="same-business-hash")
    second = dict(first)
    third = dict(first)
    first["source_raw_file_path"] = "reports/raw/first.txt"
    second["source_raw_file_path"] = "reports/raw/second.txt"
    third["source_raw_file_path"] = "reports/raw/third.txt"

    result = repo.upsert_settlement_transaction_rows(
        rows=[first, second, third], source_run_id=42
    )

    assert result.inserted_rows == 1
    assert result.updated_rows == 2
    assert len(cursor.executed) == 1
    payload = json.loads(str(cursor.executed[0][1][0]))
    assert len(payload) == 1
    assert payload[0]["source_raw_file_path"] == "reports/raw/third.txt"


def test_settlement_duplicate_hash_conflicting_identity_fails_closed() -> None:
    first = _settlement_row(row_index=1, business_key_hash="same-business-hash")
    second = _settlement_row(row_index=2, business_key_hash="same-business-hash")

    try:
        collapse_settlement_payloads_by_business_key([first, second])
    except RuntimeError as exc:
        assert "conflicting source identities" in str(exc)
    else:  # pragma: no cover - defensive test branch
        raise AssertionError("Expected RuntimeError")


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


class BatchCursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[object, ...]]] = []
        self.rowcount = 0

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        self.executed.append((sql, params))
        self.rowcount = (
            len(params) // 2 if "INNER JOIN (VALUES" in sql else len(params)
        )

    def fetchall(self) -> list[object]:
        return []


class BatchConnection:
    def __init__(self, cursor: BatchCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> BatchCursor:
        return self._cursor


def test_settlement_repo_batches_large_duplicate_deletes() -> None:
    cursor = BatchCursor()
    repo = SettlementRepo(BatchConnection(cursor))

    deleted = repo.delete_transaction_rows_by_ids(list(range(1, 2502)), batch_size=1000)

    assert deleted == 2501
    assert len(cursor.executed) == 3
    assert [len(params) for _, params in cursor.executed] == [1000, 1000, 501]


def test_settlement_repo_batches_business_key_rekeys_under_sql_parameter_limit() -> None:
    cursor = BatchCursor()
    repo = SettlementRepo(BatchConnection(cursor))
    rows = [(row_id, f"hash-{row_id}") for row_id in range(1, 2002)]

    updated = repo.update_transaction_business_key_hashes(rows, batch_size=900)

    assert updated == 2001
    assert len(cursor.executed) == 3
    assert [len(params) for _, params in cursor.executed] == [1800, 1800, 402]
    assert all("INNER JOIN (VALUES" in sql for sql, _ in cursor.executed)


def test_settlement_repo_3921_rows_use_bounded_json_merge_round_trips() -> None:
    row_count = 3921
    cursor = FakeCursor()
    repo = SettlementRepo(FakeConnection(cursor))
    rows = [
        _settlement_row(row_index=index, business_key_hash=f"business-hash-{index}")
        for index in range(1, row_count + 1)
    ]

    result = repo.upsert_settlement_transaction_rows(rows=rows, source_run_id=42)

    assert result.updated_rows == row_count
    assert len(cursor.executed) == 8
    assert all("OPENJSON" in sql for sql, _ in cursor.executed)
    assert all(len(params) == 1 for _, params in cursor.executed)
    assert sum(len(json.loads(str(params[0]))) for _, params in cursor.executed) == row_count

