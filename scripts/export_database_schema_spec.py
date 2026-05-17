from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from seller_data_pipeline.common.cli import run_cli_main
from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.db.schema_export import (
    fetch_live_schema_snapshot,
    render_schema_markdown,
    write_schema_exports,
)


def build_default_prefix() -> str:
    return "azure_sql_schema_" + datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export the current live Azure SQL schema from system catalog views. "
            "Use the output when updating docs/database/database_current_schema_spec.md."
        ),
    )
    parser.add_argument(
        "--out-dir",
        default="runtime/schema_exports",
        help="Directory for generated schema export files. Default: runtime/schema_exports.",
    )
    parser.add_argument(
        "--output-prefix",
        default=None,
        help="Output filename prefix without extension. Defaults to azure_sql_schema_YYYYMMDD_HHMMSS.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown", "both"),
        default="both",
        help="Output format. Default: both.",
    )
    parser.add_argument(
        "--include-row-counts",
        action="store_true",
        help=(
            "Include approximate live table row counts from sys.dm_db_partition_stats. "
            "Useful for audits, but omit it when you only need structural schema."
        ),
    )
    parser.add_argument(
        "--stdout-markdown",
        action="store_true",
        help="Print markdown to stdout instead of writing files. Useful for quick review.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    snapshot = fetch_live_schema_snapshot(
        settings=settings,
        include_row_counts=args.include_row_counts,
    )

    if args.stdout_markdown:
        print(render_schema_markdown(snapshot), end="")
        return

    written = write_schema_exports(
        snapshot,
        output_dir=Path(args.out_dir),
        output_prefix=args.output_prefix or build_default_prefix(),
        output_format=args.format,
    )

    print("Azure SQL live schema export completed.")
    print(f"Database: {snapshot.get('database', {}).get('database_name', '')}")
    print(f"User tables: {snapshot.get('table_count', 0)}")
    for name, path in written.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    run_cli_main(main)
