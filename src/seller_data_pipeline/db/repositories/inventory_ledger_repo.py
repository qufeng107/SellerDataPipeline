from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from seller_data_pipeline.ingestion.inventory_ledger_table_mapping import (
    INVENTORY_LEDGER_TARGET_TABLE_SPECS,
    InventoryLedgerTargetTableSpec,
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
_ALLOWED_TABLES = {spec.target_table for spec in INVENTORY_LEDGER_TARGET_TABLE_SPECS} | {
    "amazon_sync_run_log",
    "amazon_schema_validation_event",
}


@dataclass(frozen=True)
class InventoryLedgerUpsertTableResult:
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
class InventoryLedgerUpsertRunResult:
    table_results: tuple[InventoryLedgerUpsertTableResult, ...]
    sync_run_id: int | None = None

    @property
    def attempted_rows(self) -> int:
        return sum(result.attempted_rows for result in self.table_results)

    @property
    def written_rows(self) -> int:
        return sum(result.written_rows for result in self.table_results)

    @property
    def inserted_rows(self) -> int:
        return sum(result.inserted_rows for result in self.table_results)

    @property
    def updated_rows(self) -> int:
        return sum(result.updated_rows for result in self.table_results)

    @property
    def skipped_rows(self) -> int:
        return sum(result.skipped_rows for result in self.table_results)


class InventoryLedgerRepo:
    """Azure SQL repository for Inventory Ledger normalized tables."""

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
                _db_value(payload.get(column))
                for column in _SCHEMA_VALIDATION_EVENT_COLUMNS
            )
            cursor.execute(sql, params)
            inserted += 1
        return inserted

    def upsert_rows(
        self,
        *,
        table_spec: InventoryLedgerTargetTableSpec,
        rows: list[dict[str, Any]],
        source_run_id: int | None = None,
    ) -> InventoryLedgerUpsertTableResult:
        validate_inventory_ledger_table_spec(table_spec)
        sql = build_inventory_ledger_merge_sql(table_spec=table_spec)
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
        return InventoryLedgerUpsertTableResult(
            table_name=table_spec.target_table,
            report_type=table_spec.report_type,
            attempted_rows=len(rows),
            inserted_rows=inserted,
            updated_rows=updated,
            skipped_rows=skipped,
        )

    def commit(self) -> None:
        self.connection.commit()


class NullInventoryLedgerRepo:
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

    def upsert_rows(
        self,
        *,
        table_spec: InventoryLedgerTargetTableSpec,
        rows: list[dict[str, Any]],
        source_run_id: int | None = None,
    ) -> InventoryLedgerUpsertTableResult:  # noqa: ARG002
        return InventoryLedgerUpsertTableResult(
            table_name=table_spec.target_table,
            report_type=table_spec.report_type,
            attempted_rows=len(rows),
            inserted_rows=0,
            updated_rows=0,
            skipped_rows=0,
        )

    def commit(self) -> None:
        return None


def validate_inventory_ledger_table_spec(table_spec: InventoryLedgerTargetTableSpec) -> None:
    if table_spec.target_table not in _ALLOWED_TABLES:
        raise ValueError(
            "Inventory Ledger target table is not allowlisted: "
            f"{table_spec.target_table}"
        )
    for required_column in ("source_row_index", "business_key_hash"):
        if required_column not in table_spec.table_columns:
            raise ValueError(
                f"Inventory Ledger target table lacks {required_column}: {table_spec.target_table}"
            )


def build_inventory_ledger_merge_sql(*, table_spec: InventoryLedgerTargetTableSpec) -> str:
    validate_inventory_ledger_table_spec(table_spec)
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
        f"INSERT INTO dbo.{_quote_identifier(table_name)} "
        f"({column_sql}) VALUES ({placeholders});"
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
        raise ValueError(
            "Table is not allowlisted for Inventory Ledger repository writes: "
            f"{table_name}"
        )


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
    "NullInventoryLedgerRepo",
    "InventoryLedgerRepo",
    "InventoryLedgerUpsertRunResult",
    "InventoryLedgerUpsertTableResult",
    "build_insert_sql",
    "build_insert_with_output_sql",
    "build_inventory_ledger_merge_sql",
    "validate_inventory_ledger_table_spec",
]
