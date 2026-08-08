from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from seller_data_pipeline.ingestion.settlement_table_mapping import (
    SETTLEMENT_TARGET_TABLE,
    SETTLEMENT_TARGET_TABLE_SPEC,
    SettlementTargetTableSpec,
)

_SYNC_RUN_LOG_COLUMNS = (
    "workflow_name",
    "job_name",
    "task_type",
    "trigger_type",
    "run_mode",
    "parent_run_id",
    "job_execution_id",
    "marketplace_id",
    "source_system",
    "status",
    "started_at",
    "finished_at",
    "duration_ms",
    "date_start",
    "date_end",
    "rows_read",
    "rows_written",
    "rows_skipped",
    "rows_failed",
    "files_created",
    "retry_count",
    "config_snapshot_json",
    "message",
    "error_type",
    "error_detail",
)
_SCHEMA_VALIDATION_EVENT_COLUMNS = (
    "source_system",
    "marketplace_id",
    "report_type",
    "report_id",
    "raw_file_id",
    "raw_file_path",
    "validation_stage",
    "validation_status",
    "severity",
    "row_count",
    "observed_fields_json",
    "expected_fields_json",
    "missing_fields_json",
    "new_fields_json",
    "unmapped_fields_json",
    "requires_review",
    "notification_status",
    "notified_at",
    "message",
    "source_run_id",
)
_ALLOWED_TABLES = {
    SETTLEMENT_TARGET_TABLE,
    "amazon_sync_run_log",
    "amazon_schema_validation_event",
}


@dataclass(frozen=True)
class SettlementUpsertTableResult:
    table_name: str
    report_type: str
    attempted_rows: int
    inserted_rows: int
    updated_rows: int
    skipped_rows: int

    @property
    def written_rows(self) -> int:
        return self.inserted_rows + self.updated_rows


@dataclass(frozen=True)
class SettlementUpsertRunResult:
    table_result: SettlementUpsertTableResult
    sync_run_id: int | None = None

    @property
    def attempted_rows(self) -> int:
        return self.table_result.attempted_rows

    @property
    def written_rows(self) -> int:
        return self.table_result.written_rows

    @property
    def inserted_rows(self) -> int:
        return self.table_result.inserted_rows

    @property
    def updated_rows(self) -> int:
        return self.table_result.updated_rows

    @property
    def skipped_rows(self) -> int:
        return self.table_result.skipped_rows


class SettlementRepo:
    """Azure SQL repository for Settlement normalized table."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def insert_sync_run_log(self, event: dict[str, Any]) -> int:
        sql = build_insert_with_output_sql(
            table_name="amazon_sync_run_log",
            columns=_SYNC_RUN_LOG_COLUMNS,
            output_column="id",
        )
        params = tuple(_db_value(event.get(column)) for column in _SYNC_RUN_LOG_COLUMNS)
        cursor = self.connection.cursor()
        cursor.execute(sql, params)
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Azure SQL did not return amazon_sync_run_log.id")
        return int(row[0])

    def update_sync_run_log(self, sync_run_id: int, event: dict[str, Any]) -> None:
        update_columns = tuple(
            column for column in _SYNC_RUN_LOG_COLUMNS if column not in {"started_at"}
        )
        set_sql = ", ".join(f"{_quote_identifier(column)} = ?" for column in update_columns)
        sql = f"UPDATE dbo.[amazon_sync_run_log] SET {set_sql} WHERE [id] = ?;"
        params = tuple(_db_value(event.get(column)) for column in update_columns) + (sync_run_id,)
        cursor = self.connection.cursor()
        cursor.execute(sql, params)

    def insert_schema_validation_events(
        self,
        events: list[dict[str, Any]],
        *,
        source_run_id: int | None,
    ) -> int:
        if not events:
            return 0
        sql = build_insert_sql(
            table_name="amazon_schema_validation_event",
            columns=_SCHEMA_VALIDATION_EVENT_COLUMNS,
        )
        cursor = self.connection.cursor()
        inserted = 0
        for event in events:
            payload = dict(event)
            payload["source_run_id"] = source_run_id
            params = tuple(
                _db_value(payload.get(column)) for column in _SCHEMA_VALIDATION_EVENT_COLUMNS
            )
            cursor.execute(sql, params)
            inserted += 1
        return inserted

    def upsert_settlement_transaction_rows(
        self,
        *,
        rows: list[dict[str, Any]],
        source_run_id: int | None = None,
        table_spec: SettlementTargetTableSpec = SETTLEMENT_TARGET_TABLE_SPEC,
    ) -> SettlementUpsertTableResult:
        validate_settlement_table_spec(table_spec)
        sql = build_settlement_merge_sql(table_spec=table_spec)
        cursor = self.connection.cursor()
        inserted = 0
        updated = 0
        skipped = 0
        columns = table_spec.table_columns
        for row in rows:
            if not row.get("business_key_hash") or row.get("source_row_index") is None:
                skipped += 1
                continue
            payload = dict(row)
            payload["source_run_id"] = source_run_id
            params = tuple(_db_value(payload.get(column)) for column in columns)
            cursor.execute(sql, params)
            action_row = cursor.fetchone()
            action = _read_merge_action(action_row)
            if action == "INSERT":
                inserted += 1
            elif action == "UPDATE":
                updated += 1
            else:
                updated += 1
        return SettlementUpsertTableResult(
            table_name=table_spec.target_table,
            report_type=table_spec.report_type,
            attempted_rows=len(rows),
            inserted_rows=inserted,
            updated_rows=updated,
            skipped_rows=skipped,
        )

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def fetch_duplicate_source_identities(
        self, *, marketplace_id: str | None = None
    ) -> list[dict[str, Any]]:
        where = (
            "AND [marketplace_id] = ?" if marketplace_id else ""
        )
        sql = f"""
            SELECT
                [marketplace_id],
                [source_report_id],
                [source_row_index],
                [source_row_hash],
                COUNT(*) AS [duplicate_count]
            FROM dbo.[amazon_settlement_transaction]
            WHERE [source_report_id] IS NOT NULL
              AND [source_row_index] IS NOT NULL
              AND [source_row_hash] IS NOT NULL
              {where}
            GROUP BY
                [marketplace_id],
                [source_report_id],
                [source_row_index],
                [source_row_hash]
            HAVING COUNT(*) > 1
            ORDER BY [marketplace_id], [source_report_id], [source_row_index];
        """
        params = (marketplace_id,) if marketplace_id else ()
        cursor = self.connection.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [
            {
                "marketplace_id": row[0],
                "source_report_id": row[1],
                "source_row_index": int(row[2]),
                "source_row_hash": row[3],
                "duplicate_count": int(row[4]),
            }
            for row in rows
        ]

    def fetch_source_identity_rows(
        self,
        *,
        marketplace_id: str,
        source_report_id: str,
        source_row_index: int,
        source_row_hash: str,
    ) -> list[dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT [id], [business_key_hash], [source_raw_file_path], [source_run_id]
            FROM dbo.[amazon_settlement_transaction]
            WHERE [marketplace_id] = ?
              AND [source_report_id] = ?
              AND [source_row_index] = ?
              AND [source_row_hash] = ?
            ORDER BY [id];
            """,
            (marketplace_id, source_report_id, source_row_index, source_row_hash),
        )
        return [
            {
                "id": int(row[0]),
                "business_key_hash": row[1],
                "source_raw_file_path": row[2],
                "source_run_id": row[3],
            }
            for row in cursor.fetchall()
        ]

    def fetch_business_key_owner(self, business_key_hash: str) -> dict[str, Any] | None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT TOP (1)
                [id], [marketplace_id], [source_report_id], [source_row_index],
                [source_row_hash], [business_key_hash]
            FROM dbo.[amazon_settlement_transaction]
            WHERE [business_key_hash] = ?;
            """,
            (business_key_hash,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return {
            "id": int(row[0]),
            "marketplace_id": row[1],
            "source_report_id": row[2],
            "source_row_index": row[3],
            "source_row_hash": row[4],
            "business_key_hash": row[5],
        }

    def delete_transaction_rows_by_ids(self, row_ids: list[int]) -> int:
        if not row_ids:
            return 0
        placeholders = ", ".join("?" for _ in row_ids)
        cursor = self.connection.cursor()
        cursor.execute(
            f"DELETE FROM dbo.[amazon_settlement_transaction] WHERE [id] IN ({placeholders});",
            tuple(int(row_id) for row_id in row_ids),
        )
        return int(cursor.rowcount if cursor.rowcount is not None and cursor.rowcount >= 0 else len(row_ids))

    def update_transaction_business_key_hash(
        self, *, row_id: int, business_key_hash: str
    ) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            UPDATE dbo.[amazon_settlement_transaction]
            SET [business_key_hash] = ?, [updated_at] = SYSUTCDATETIME()
            WHERE [id] = ?;
            """,
            (business_key_hash, int(row_id)),
        )


class NullSettlementRepo:
    """No-op repository used by tests that need the same interface."""

    def insert_sync_run_log(self, event: dict[str, Any]) -> int:  # noqa: ARG002
        return 0

    def update_sync_run_log(self, sync_run_id: int, event: dict[str, Any]) -> None:  # noqa: ARG002
        return None

    def insert_schema_validation_events(
        self,
        events: list[dict[str, Any]],
        *,
        source_run_id: int | None,
    ) -> int:  # noqa: ARG002
        return len(events)

    def upsert_settlement_transaction_rows(
        self,
        *,
        rows: list[dict[str, Any]],
        source_run_id: int | None = None,
        table_spec: SettlementTargetTableSpec = SETTLEMENT_TARGET_TABLE_SPEC,
    ) -> SettlementUpsertTableResult:  # noqa: ARG002
        return SettlementUpsertTableResult(
            table_name=table_spec.target_table,
            report_type=table_spec.report_type,
            attempted_rows=len(rows),
            inserted_rows=0,
            updated_rows=0,
            skipped_rows=0,
        )

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


def validate_settlement_table_spec(table_spec: SettlementTargetTableSpec) -> None:
    if table_spec.target_table != SETTLEMENT_TARGET_TABLE:
        raise ValueError(f"Settlement target table is not allowlisted: {table_spec.target_table}")
    for required_column in ("source_row_index", "business_key_hash"):
        if required_column not in table_spec.table_columns:
            raise ValueError(
                f"Settlement target table lacks {required_column}: {table_spec.target_table}"
            )


def build_settlement_merge_sql(*, table_spec: SettlementTargetTableSpec) -> str:
    validate_settlement_table_spec(table_spec)
    columns = table_spec.table_columns
    source_select = ", ".join(f"? AS {_quote_identifier(column)}" for column in columns)
    update_columns = [column for column in columns if column not in {"business_key_hash"}]
    update_set = ",\n        ".join(
        f"target.{_quote_identifier(column)} = source.{_quote_identifier(column)}"
        for column in update_columns
    )
    update_set = update_set + ",\n        target.[updated_at] = SYSUTCDATETIME()"
    insert_columns = ", ".join(_quote_identifier(column) for column in columns)
    insert_values = ", ".join(f"source.{_quote_identifier(column)}" for column in columns)
    return (
        f"MERGE dbo.{_quote_identifier(table_spec.target_table)} WITH (HOLDLOCK) AS target\n"
        f"USING (SELECT {source_select}) AS source\n"
        "ON target.[business_key_hash] = source.[business_key_hash]\n"
        "WHEN MATCHED THEN\n"
        f"    UPDATE SET {update_set}\n"
        "WHEN NOT MATCHED THEN\n"
        f"    INSERT ({insert_columns})\n"
        f"    VALUES ({insert_values})\n"
        "OUTPUT $action AS merge_action;"
    )


def build_insert_sql(*, table_name: str, columns: tuple[str, ...]) -> str:
    validate_static_table_name(table_name)
    column_sql = ", ".join(_quote_identifier(column) for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    return (
        f"INSERT INTO dbo.{_quote_identifier(table_name)} ({column_sql}) VALUES ({placeholders});"
    )


def build_insert_with_output_sql(
    *,
    table_name: str,
    columns: tuple[str, ...],
    output_column: str,
) -> str:
    validate_static_table_name(table_name)
    column_sql = ", ".join(_quote_identifier(column) for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    return (
        f"INSERT INTO dbo.{_quote_identifier(table_name)} ({column_sql})\n"
        f"OUTPUT INSERTED.{_quote_identifier(output_column)}\n"
        f"VALUES ({placeholders});"
    )


def validate_static_table_name(table_name: str) -> None:
    if table_name not in _ALLOWED_TABLES:
        raise ValueError(f"Table is not allowlisted for Settlement repository writes: {table_name}")


def _quote_identifier(identifier: str) -> str:
    if not identifier or not identifier.replace("_", "").isalnum():
        raise ValueError(f"Unsafe SQL identifier: {identifier!r}")
    return f"[{identifier}]"


def _db_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (dict, list, tuple)):
        import json

        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return value


def _read_merge_action(action_row: Any) -> str | None:
    if action_row is None:
        return None
    try:
        return str(action_row[0]).upper()
    except (IndexError, TypeError):
        return str(action_row).upper()


__all__ = [
    "NullSettlementRepo",
    "SettlementRepo",
    "SettlementUpsertRunResult",
    "SettlementUpsertTableResult",
    "build_insert_sql",
    "build_insert_with_output_sql",
    "build_settlement_merge_sql",
    "validate_settlement_table_spec",
]
