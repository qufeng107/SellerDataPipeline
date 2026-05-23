from __future__ import annotations

import argparse
import logging
from pathlib import Path

from seller_data_pipeline.common.cli import run_cli_main
from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.db.migrations import read_sql_batches, run_sql_file

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one Azure SQL migration file.")
    parser.add_argument(
        "--file",
        required=True,
        help=(
            "Path to a single SQL migration file, for example "
            "sql/migrations/001_create_core_tables.sql."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Only parse the file and print the executable batch count. "
            "No database connection is opened."
        ),
    )
    parser.add_argument(
        "--show-batches",
        action="store_true",
        help="Print the first line of each executable batch for review.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    file_path = Path(args.file)
    if args.show_batches:
        batches = read_sql_batches(file_path)
        print(f"{file_path}: {len(batches)} executable batches")
        for index, batch in enumerate(batches, start=1):
            first_line = next((line.strip() for line in batch.splitlines() if line.strip()), "")
            print(f"{index:03d}: {first_line[:140]}")
        if args.dry_run:
            return

    result = run_sql_file(file_path, settings=settings, dry_run=args.dry_run)

    if result.dry_run:
        print(
            f"Dry run passed: {result.file_path} contains {result.batch_count} executable batches."
        )
        return

    logger.info(
        "Migration executed successfully. file=%s executed_batches=%s/%s",
        result.file_path,
        result.executed_batch_count,
        result.batch_count,
    )
    print(
        f"Migration executed successfully: {result.file_path} "
        f"({result.executed_batch_count}/{result.batch_count} batches)."
    )


if __name__ == "__main__":
    run_cli_main(main)
