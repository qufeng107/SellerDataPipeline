from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from seller_data_pipeline.common.cli import run_cli_main
from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.db.connection import (
    get_connection,
    list_user_tables,
    run_connection_diagnostics,
)

logger = logging.getLogger(__name__)

DEFAULT_COUNT_TABLES = (
    "amazon_ads_sp_campaign_daily",
    "amazon_ads_sp_targeting_daily",
    "amazon_ads_sp_search_term_daily",
    "amazon_ads_sp_advertised_product_daily",
    "amazon_sync_run_log",
    "amazon_schema_validation_event",
    "amazon_raw_report_file",
    "amazon_listing_snapshot",
    "amazon_inventory_daily",
    "amazon_sales_traffic_daily",
    "amazon_sales_traffic_asin_daily",
    "amazon_settlement_transaction",
)

LATEST_SYNC_RUN_COLUMNS = (
    "id",
    "workflow_name",
    "job_name",
    "task_type",
    "run_mode",
    "source_system",
    "marketplace_id",
    "status",
    "started_at",
    "finished_at",
    "duration_ms",
    "rows_read",
    "rows_written",
    "rows_skipped",
    "rows_failed",
    "message",
    "error_type",
    "error_detail",
)

LATEST_SCHEMA_EVENT_COLUMNS = (
    "id",
    "source_system",
    "marketplace_id",
    "report_type",
    "report_id",
    "validation_stage",
    "validation_status",
    "severity",
    "row_count",
    "requires_review",
    "notification_status",
    "message",
    "source_run_id",
    "created_at",
)


def validate_table_name(table_name: str) -> str:
    """Return a safe table identifier or raise ValueError.

    Table names are injected into SQL because SQL Server cannot bind identifiers as
    parameters. Keep this function strict and only allow dbo user tables shaped like
    the project migration names.
    """

    if not table_name or not table_name.replace("_", "").isalnum():
        raise ValueError(f"Unsafe table name: {table_name!r}")
    return table_name


def quote_identifier(identifier: str) -> str:
    validate_table_name(identifier)
    return f"[{identifier}]"


def build_table_count_query(table_names: list[str] | tuple[str, ...]) -> str:
    if not table_names:
        raise ValueError("At least one table name is required")
    selects = []
    for table_name in table_names:
        safe_name = validate_table_name(table_name)
        selects.append(
            "SELECT "
            f"'{safe_name}' AS table_name, "
            f"COUNT_BIG(*) AS rows_count FROM dbo.{quote_identifier(safe_name)}"
        )
    return "\nUNION ALL\n".join(selects) + ";"


def fetch_table_counts(connection: Any, table_names: list[str]) -> list[dict[str, Any]]:
    if not table_names:
        return []
    cursor = connection.cursor()
    try:
        cursor.execute(build_table_count_query(table_names))
        return rows_to_dicts(cursor)
    finally:
        cursor.close()


def fetch_latest_sync_runs(connection: Any, *, limit: int) -> list[dict[str, Any]]:
    cursor = connection.cursor()
    try:
        columns_sql = ",\n            ".join(
            quote_identifier(column) for column in LATEST_SYNC_RUN_COLUMNS
        )
        cursor.execute(
            f"""
            SELECT TOP (?)
                {columns_sql}
            FROM dbo.[amazon_sync_run_log]
            ORDER BY [id] DESC;
            """,
            (limit,),
        )
        return rows_to_dicts(cursor)
    finally:
        cursor.close()


def fetch_latest_schema_validation_events(
    connection: Any,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    cursor = connection.cursor()
    try:
        columns_sql = ",\n            ".join(
            quote_identifier(column) for column in LATEST_SCHEMA_EVENT_COLUMNS
        )
        cursor.execute(
            f"""
            SELECT TOP (?)
                {columns_sql}
            FROM dbo.[amazon_schema_validation_event]
            ORDER BY [id] DESC;
            """,
            (limit,),
        )
        return rows_to_dicts(cursor)
    finally:
        cursor.close()


def rows_to_dicts(cursor: Any) -> list[dict[str, Any]]:
    columns = [column[0] for column in cursor.description]
    return [
        {column: json_ready(value) for column, value in zip(columns, row, strict=False)}
        for row in cursor.fetchall()
    ]


def json_ready(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def print_table(title: str, rows: list[dict[str, Any]]) -> None:
    print(f"\n{title}")
    if not rows:
        print("  (no rows)")
        return
    columns = list(rows[0])
    widths = {
        column: max(len(column), *(len(_display_value(row.get(column))) for row in rows))
        for column in columns
    }
    header = " | ".join(column.ljust(widths[column]) for column in columns)
    separator = "-+-".join("-" * widths[column] for column in columns)
    print(header)
    print(separator)
    for row in rows:
        values = [_display_value(row.get(column)).ljust(widths[column]) for column in columns]
        print(" | ".join(values))


def _display_value(value: Any) -> str:
    if value is None:
        return "NULL"
    text = str(value).replace("\n", " ")
    return text if len(text) <= 140 else text[:137] + "..."


def resolve_count_tables(*, all_tables: bool, table_names: list[str] | None) -> list[str]:
    if table_names:
        return [validate_table_name(table_name) for table_name in table_names]
    if not all_tables:
        return list(DEFAULT_COUNT_TABLES)
    return []


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check Azure SQL table counts and latest ingestion audit records.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the status payload as JSON.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of latest sync/schema records to show. Default: 10.",
    )
    parser.add_argument(
        "--all-tables",
        action="store_true",
        help="Count every user table instead of the default high-value operational tables.",
    )
    parser.add_argument(
        "--table",
        dest="tables",
        action="append",
        help="Specific table to count. Can be repeated. Overrides default table list.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    diagnostics = run_connection_diagnostics(settings=settings)
    user_tables = list_user_tables(settings=settings)
    available_table_names = [table["table_name"] for table in user_tables]
    count_tables = resolve_count_tables(all_tables=args.all_tables, table_names=args.tables)
    if args.all_tables and not args.tables:
        count_tables = available_table_names
    missing_tables = [table for table in count_tables if table not in available_table_names]
    existing_count_tables = [table for table in count_tables if table in available_table_names]

    with get_connection(settings=settings) as connection:
        table_counts = fetch_table_counts(connection, existing_count_tables)
        latest_sync_runs = fetch_latest_sync_runs(connection, limit=args.limit)
        latest_schema_events = fetch_latest_schema_validation_events(
            connection,
            limit=args.limit,
        )

    payload = {
        "diagnostics": diagnostics,
        "missing_tables": missing_tables,
        "table_counts": table_counts,
        "latest_sync_runs": latest_sync_runs,
        "latest_schema_validation_events": latest_schema_events,
    }

    logger.info(
        "Azure SQL status check succeeded. "
        "database=%s counted_tables=%s sync_runs=%s schema_events=%s",
        diagnostics["database_name"],
        len(table_counts),
        len(latest_sync_runs),
        len(latest_schema_events),
    )

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    print("Azure SQL status check succeeded.")
    print(f"Database: {diagnostics['database_name']}")
    print(f"Server: {diagnostics['server_name']}")
    print(f"User tables: {diagnostics['user_table_count']}")
    if missing_tables:
        print("Missing tables skipped: " + ", ".join(missing_tables))
    print_table("Table row counts", table_counts)
    print_table("Latest sync runs", latest_sync_runs)
    print_table("Latest schema validation events", latest_schema_events)


if __name__ == "__main__":
    run_cli_main(main)
