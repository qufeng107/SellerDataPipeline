from __future__ import annotations

import argparse
import json
import logging

from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.db.connection import list_user_tables, run_connection_diagnostics

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Test Azure SQL connectivity.")
    parser.add_argument(
        "--list-tables",
        action="store_true",
        help="List user-created tables after the connection test succeeds.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the diagnostic result as JSON.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    result = run_connection_diagnostics(settings=settings)
    logger.info(
        "Azure SQL connection test succeeded. database=%s tables=%s",
        result["database_name"],
        result["user_table_count"],
    )

    if args.list_tables:
        result["tables"] = list_user_tables(settings=settings)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    print("Azure SQL connection test succeeded.")
    print(f"Database: {result['database_name']}")
    print(f"Login: {result['login_name']}")
    print(f"Server: {result['server_name']}")
    print(f"Edition: {result['edition']}")
    print(f"User tables: {result['user_table_count']}")

    if args.list_tables:
        print("Tables:")
        for table in result["tables"]:
            print(f"- {table['schema_name']}.{table['table_name']}")


if __name__ == "__main__":
    main()
