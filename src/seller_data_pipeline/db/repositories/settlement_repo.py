from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import json
import logging
from typing import Any

from seller_data_pipeline.ingestion.settlement_table_mapping import (
    SETTLEMENT_TARGET_TABLE,
    SETTLEMENT_TARGET_TABLE_SPEC,
    SettlementTargetTableSpec,
)


logger = logging.getLogger(__name__)

_SETTLEMENT_JSON_SQL_TYPES: dict[str, str] = {
    "marketplace_id": "NVARCHAR(50)",
    "settlement_id": "NVARCHAR(200)",
    "settlement_start_date_raw": "NVARCHAR(100)",
    "settlement_end_date_raw": "NVARCHAR(100)",
    "deposit_date_raw": "NVARCHAR(100)",
    "total_amount": "DECIMAL(18,4)",
    "currency": "NVARCHAR(10)",
    "is_settlement_summary": "BIT",
    "transaction_type": "NVARCHAR(120)",
    "order_id": "NVARCHAR(200)",
    "merchant_order_id": "NVARCHAR(200)",
    "adjustment_id": "NVARCHAR(200)",
    "shipment_id": "NVARCHAR(200)",
    "marketplace_name": "NVARCHAR(200)",
    "amount_type": "NVARCHAR(120)",
    "amount_description": "NVARCHAR(300)",
    "amount": "DECIMAL(18,4)",
    "amount_category": "NVARCHAR(120)",
    "profit_bucket": "NVARCHAR(120)",
    "fulfillment_id": "NVARCHAR(100)",
    "posted_date_raw": "NVARCHAR(100)",
    "posted_date_time_raw": "NVARCHAR(100)",
    "order_item_code": "NVARCHAR(200)",
    "merchant_order_item_id": "NVARCHAR(200)",
    "merchant_adjustment_item_id": "NVARCHAR(200)",
    "seller_sku": "NVARCHAR(200)",
    "quantity_purchased": "INT",
    "promotion_id": "NVARCHAR(500)",
    "source_system": "NVARCHAR(50)",
    "source_report_type": "NVARCHAR(120)",
    "source_report_id": "NVARCHAR(120)",
    "source_report_request_id": "BIGINT",
    "source_raw_file_id": "BIGINT",
    "source_raw_file_path": "NVARCHAR(1000)",
    "source_run_id": "BIGINT",
    "source_row_hash": "NVARCHAR(100)",
    "raw_data": "NVARCHAR(MAX)",
    "source_row_index": "INT",
    "business_key_hash": "NVARCHAR(100)",
}
_DEFAULT_SETTLEMENT_JSON_BATCH_SIZE = 500

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
        json_batch_size: int = _DEFAULT_SETTLEMENT_JSON_BATCH_SIZE,
    ) -> SettlementUpsertTableResult:
        """Upsert Settlement rows with bounded set-based JSON MERGE batches.

        Duplicate business keys are collapsed in input order with last-write-wins
        semantics, matching the final target state of the legacy sequential MERGE.
        A duplicate hash that maps to a different immutable source identity is
        treated as a financial-integrity conflict and fails closed.
        """
        validate_settlement_table_spec(table_spec)
        validate_settlement_json_sql_types(table_spec=table_spec)
        if json_batch_size < 1:
            raise ValueError("json_batch_size must be >= 1")

        valid_payloads: list[dict[str, Any]] = []
        skipped = 0
        for row in rows:
            if not row.get("business_key_hash") or row.get("source_row_index") is None:
                skipped += 1
                continue
            payload = dict(row)
            payload["source_run_id"] = source_run_id
            valid_payloads.append(payload)

        if not valid_payloads:
            return SettlementUpsertTableResult(
                table_name=table_spec.target_table,
                report_type=table_spec.report_type,
                attempted_rows=len(rows),
                inserted_rows=0,
                updated_rows=0,
                skipped_rows=skipped,
            )

        collapsed_payloads, collapsed_duplicate_rows = collapse_settlement_payloads_by_business_key(
            valid_payloads
        )
        batch_count = (len(collapsed_payloads) + json_batch_size - 1) // json_batch_size
        logger.info(
            "Settlement JSON set-based upsert input_rows=%s unique_business_keys=%s "
            "collapsed_duplicate_rows=%s batch_size=%s batches=%s",
            len(valid_payloads),
            len(collapsed_payloads),
            collapsed_duplicate_rows,
            json_batch_size,
            batch_count,
        )

        cursor = self.connection.cursor()
        merge_sql = build_settlement_json_merge_sql(table_spec=table_spec)
        inserted = 0
        merged_unique_rows = 0
        for batch_number, start in enumerate(
            range(0, len(collapsed_payloads), json_batch_size),
            start=1,
        ):
            batch = collapsed_payloads[start : start + json_batch_size]
            source_json = build_settlement_json_payload(rows=batch, table_spec=table_spec)
            logger.info(
                "Settlement JSON MERGE batch=%s/%s rows=%s json_bytes=%s",
                batch_number,
                batch_count,
                len(batch),
                len(source_json.encode("utf-8")),
            )
            cursor.execute(merge_sql, (source_json,))
            action_rows = list(cursor.fetchall())
            if len(action_rows) != len(batch):
                raise RuntimeError(
                    "Settlement JSON MERGE action count mismatch: "
                    f"batch={batch_number}/{batch_count} "
                    f"expected={len(batch)} actual={len(action_rows)}"
                )
            for action_row in action_rows:
                action = _read_merge_action(action_row)
                if action == "INSERT":
                    inserted += 1
                elif action != "UPDATE":
                    raise RuntimeError(
                        f"Settlement JSON MERGE returned unexpected action: {action!r}"
                    )
            merged_unique_rows += len(batch)

        if merged_unique_rows != len(collapsed_payloads):
            raise RuntimeError(
                "Settlement JSON MERGE unique-row count mismatch: "
                f"expected={len(collapsed_payloads)} actual={merged_unique_rows}"
            )

        # Preserve legacy sequential audit semantics. For a duplicate key with k
        # input rows, a missing target would have produced one INSERT followed by
        # k-1 UPDATEs; an existing target would have produced k UPDATEs.
        updated = len(valid_payloads) - inserted
        logger.info(
            "Settlement JSON set-based upsert completed attempted=%s unique_business_keys=%s "
            "collapsed_duplicate_rows=%s inserted=%s updated=%s skipped=%s",
            len(rows),
            len(collapsed_payloads),
            collapsed_duplicate_rows,
            inserted,
            updated,
            skipped,
        )
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

    def fetch_idempotency_repair_rows(
        self, *, marketplace_id: str | None = None
    ) -> list[dict[str, Any]]:
        where = "WHERE [marketplace_id] = ?" if marketplace_id else ""
        sql = f"""
            SELECT
                [id],
                [marketplace_id],
                [source_report_id],
                [source_row_index],
                [source_row_hash],
                [business_key_hash],
                [source_raw_file_path],
                [source_run_id]
            FROM dbo.[amazon_settlement_transaction]
            {where}
            ORDER BY [id];
        """
        params = (marketplace_id,) if marketplace_id else ()
        cursor = self.connection.cursor()
        cursor.execute(sql, params)
        return [
            {
                "id": int(row[0]),
                "marketplace_id": row[1],
                "source_report_id": row[2],
                "source_row_index": int(row[3]) if row[3] is not None else None,
                "source_row_hash": row[4],
                "business_key_hash": row[5],
                "source_raw_file_path": row[6],
                "source_run_id": row[7],
            }
            for row in cursor.fetchall()
        ]

    def delete_transaction_rows_by_ids(
        self, row_ids: list[int], *, batch_size: int = 1000
    ) -> int:
        if not row_ids:
            return 0
        if batch_size < 1 or batch_size > 2000:
            raise ValueError("batch_size must be between 1 and 2000")
        deleted = 0
        for start in range(0, len(row_ids), batch_size):
            batch = row_ids[start : start + batch_size]
            placeholders = ", ".join("?" for _ in batch)
            cursor = self.connection.cursor()
            cursor.execute(
                f"DELETE FROM dbo.[amazon_settlement_transaction] "
                f"WHERE [id] IN ({placeholders});",
                tuple(int(row_id) for row_id in batch),
            )
            deleted += int(
                cursor.rowcount
                if cursor.rowcount is not None and cursor.rowcount >= 0
                else len(batch)
            )
        return deleted

    def update_transaction_business_key_hashes(
        self,
        rows: list[tuple[int, str]],
        *,
        batch_size: int = 900,
    ) -> int:
        if not rows:
            return 0
        if batch_size < 1 or batch_size > 1000:
            raise ValueError("batch_size must be between 1 and 1000")
        updated = 0
        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            value_sql = ", ".join("(?, ?)" for _ in batch)
            sql = f"""
                UPDATE target
                SET
                    target.[business_key_hash] = source.[business_key_hash],
                    target.[updated_at] = SYSUTCDATETIME()
                FROM dbo.[amazon_settlement_transaction] AS target
                INNER JOIN (VALUES {value_sql}) AS source([id], [business_key_hash])
                    ON target.[id] = source.[id];
            """
            params: list[Any] = []
            for row_id, business_key_hash in batch:
                params.extend((int(row_id), business_key_hash))
            cursor = self.connection.cursor()
            cursor.execute(sql, tuple(params))
            updated += int(
                cursor.rowcount
                if cursor.rowcount is not None and cursor.rowcount >= 0
                else len(batch)
            )
        return updated


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
        json_batch_size: int = _DEFAULT_SETTLEMENT_JSON_BATCH_SIZE,
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


def validate_settlement_json_sql_types(*, table_spec: SettlementTargetTableSpec) -> None:
    expected = set(table_spec.table_columns)
    configured = set(_SETTLEMENT_JSON_SQL_TYPES)
    if configured != expected:
        missing = sorted(expected - configured)
        extra = sorted(configured - expected)
        raise ValueError(
            "Settlement JSON SQL type mapping is out of sync with table mapping: "
            f"missing={missing} extra={extra}"
        )


def collapse_settlement_payloads_by_business_key(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Collapse exact duplicate business keys using deterministic last-write-wins.

    A business-key hash is derived from the immutable source identity. If the
    same hash appears with a different identity, do not assume it is safe: fail
    closed so the transaction can roll back and the data can be investigated.
    """
    by_key: dict[str, dict[str, Any]] = {}
    identities: dict[str, tuple[Any, Any, Any, Any]] = {}
    for payload in rows:
        key = str(payload["business_key_hash"])
        identity = (
            payload.get("marketplace_id"),
            payload.get("source_report_id"),
            payload.get("source_row_index"),
            payload.get("source_row_hash"),
        )
        existing_identity = identities.get(key)
        if existing_identity is not None and existing_identity != identity:
            raise RuntimeError(
                "Settlement duplicate business_key_hash maps to conflicting source identities: "
                f"business_key_hash={key} first={existing_identity!r} next={identity!r}"
            )
        identities[key] = identity
        # Assignment replaces the payload so the final target values match the
        # legacy sequential path's last occurrence for this exact source identity.
        by_key[key] = payload
    collapsed = list(by_key.values())
    return collapsed, len(rows) - len(collapsed)


def build_settlement_json_payload(
    *,
    rows: list[dict[str, Any]],
    table_spec: SettlementTargetTableSpec,
) -> str:
    validate_settlement_table_spec(table_spec)
    validate_settlement_json_sql_types(table_spec=table_spec)
    payload_rows = [
        {column: _json_parameter_value(row.get(column)) for column in table_spec.table_columns}
        for row in rows
    ]
    return json.dumps(payload_rows, ensure_ascii=False, separators=(",", ":"))


def build_settlement_json_merge_sql(*, table_spec: SettlementTargetTableSpec) -> str:
    validate_settlement_table_spec(table_spec)
    validate_settlement_json_sql_types(table_spec=table_spec)
    columns = table_spec.table_columns
    openjson_columns = ",\n        ".join(
        f"{_quote_identifier(column)} {_SETTLEMENT_JSON_SQL_TYPES[column]} '$.{column}'"
        for column in columns
    )
    update_columns = [column for column in columns if column != "business_key_hash"]
    update_set = ",\n        ".join(
        f"target.{_quote_identifier(column)} = source.{_quote_identifier(column)}"
        for column in update_columns
    )
    update_set += ",\n        target.[updated_at] = SYSUTCDATETIME()"
    insert_columns = ", ".join(_quote_identifier(column) for column in columns)
    insert_values = ", ".join(f"source.{_quote_identifier(column)}" for column in columns)
    return (
        f"MERGE dbo.{_quote_identifier(table_spec.target_table)} WITH (HOLDLOCK) AS target\n"
        "USING (\n"
        "    SELECT *\n"
        "    FROM OPENJSON(CAST(? AS NVARCHAR(MAX)))\n"
        f"    WITH (\n        {openjson_columns}\n    )\n"
        ") AS source\n"
        "ON target.[business_key_hash] = source.[business_key_hash]\n"
        "WHEN MATCHED THEN\n"
        f"    UPDATE SET {update_set}\n"
        "WHEN NOT MATCHED THEN\n"
        f"    INSERT ({insert_columns})\n"
        f"    VALUES ({insert_values})\n"
        "OUTPUT $action AS merge_action;"
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
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return value


def _json_parameter_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (dict, list, tuple)):
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
    "build_settlement_json_merge_sql",
    "build_settlement_json_payload",
    "collapse_settlement_payloads_by_business_key",
    "validate_settlement_json_sql_types",
    "validate_settlement_table_spec",
]
