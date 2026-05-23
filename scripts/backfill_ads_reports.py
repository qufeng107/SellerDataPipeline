from __future__ import annotations

import argparse
from datetime import date

from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.services.historical_backfill_service import BackfillAdsReportsService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Submit Amazon Ads Reporting v3 requests over explicit historical chunks."
    )
    parser.add_argument(
        "--profile-id",
        help="Amazon Ads profile ID. Defaults to AMAZON_ADS_PROFILE_ID.",
    )
    parser.add_argument("--start-date", required=True, help="Inclusive start date, YYYY-MM-DD.")
    parser.add_argument("--end-date", required=True, help="Inclusive end date, YYYY-MM-DD.")
    parser.add_argument(
        "--chunk-days",
        type=int,
        default=14,
        help="Inclusive calendar days per Ads request chunk. Default: 14.",
    )
    parser.add_argument(
        "--only-report-type-id",
        action="append",
        default=[],
        help="Run only the specified Ads reportTypeId. Can be passed multiple times.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually submit requests. Default is dry-run preview only.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Submit even if a matching local Ads manifest exists.",
    )
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=2.0,
        help="Delay between Amazon Ads calls to reduce throttling risk. Default: 2.0.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    result = BackfillAdsReportsService(settings=settings).run(
        profile_id=args.profile_id,
        start_date=date.fromisoformat(args.start_date),
        end_date=date.fromisoformat(args.end_date),
        chunk_days=args.chunk_days,
        only_report_type_ids=args.only_report_type_id or None,
        dry_run=not args.execute,
        force=args.force,
        pause_seconds=args.pause_seconds,
    )

    print(
        "Amazon Ads backfill "
        f"status={'dry_run' if result.dry_run else 'submitted'} "
        f"total={result.total_count} created={result.created_count} "
        f"skipped_existing={result.skipped_count} failed={result.failed_count}"
    )
    for row in result.window_results:
        suffix = f" manifest={row.manifest_path}" if row.manifest_path else ""
        message = f" message={row.message}" if row.message else ""
        print(
            f"{row.status}: {row.report_type} {row.start_date}..{row.end_date}"
            f"{suffix}{message}"
        )
    if result.dry_run:
        print("Dry-run only. Re-run with --execute after reviewing the planned chunks.")


if __name__ == "__main__":
    main()
