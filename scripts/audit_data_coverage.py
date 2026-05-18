from __future__ import annotations

import argparse
from datetime import date

from seller_data_pipeline.common.cli import run_cli_main
from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.db.connection import get_connection
from seller_data_pipeline.db.repositories.data_coverage_repo import DataCoverageRepo
from seller_data_pipeline.services.data_coverage_service import DataCoverageAuditService


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audit normalized Amazon data coverage by source table and business date. "
            "This is read-only and writes local JSON/Markdown/CSV review files."
        )
    )
    parser.add_argument(
        "--marketplace-id",
        default=None,
        help="Amazon marketplace ID, for example ATVPDKIKX0DER. Defaults to .env.",
    )
    parser.add_argument(
        "--target-start-date",
        default="2026-01-01",
        help="Target coverage start date, YYYY-MM-DD. Defaults to 2026-01-01.",
    )
    parser.add_argument(
        "--target-end-date",
        default=None,
        help="Target coverage end date, YYYY-MM-DD. Defaults to today's local date.",
    )
    parser.add_argument(
        "--output-root",
        default="runtime/data_coverage_audits",
        help="Output root for audit files.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    marketplace_id = args.marketplace_id or settings.amazon_marketplace_id
    if not marketplace_id:
        raise SystemExit("Missing --marketplace-id or AMAZON_MARKETPLACE_ID.")

    target_start_date = date.fromisoformat(args.target_start_date)
    target_end_date = date.fromisoformat(args.target_end_date) if args.target_end_date else date.today()

    with get_connection(settings=settings, autocommit=True) as connection:
        service = DataCoverageAuditService(repo=DataCoverageRepo(connection))
        result = service.run(
            marketplace_id=marketplace_id,
            target_start_date=target_start_date,
            target_end_date=target_end_date,
            output_root=args.output_root,
        )

    print("Data coverage audit completed.")
    print(f"marketplace={result.marketplace_id}")
    print(f"target_window={result.target_start_date}..{result.target_end_date}")
    print("status_counts=" + ", ".join(f"{k}:{v}" for k, v in sorted(result.status_counts.items())))
    for name, path in result.output_files.items():
        print(f"{name}={path}")


if __name__ == "__main__":
    run_cli_main(main)
