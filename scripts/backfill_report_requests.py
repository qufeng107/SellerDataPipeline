from __future__ import annotations

import argparse
from datetime import date

from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.services.historical_backfill_service import BackfillReportRequestsService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Submit SP-API report requests over explicit historical date chunks."
    )
    parser.add_argument("--report-type", required=True, help="Amazon SP-API report type.")
    parser.add_argument(
        "--marketplace-id",
        action="append",
        dest="marketplace_ids",
        help="Marketplace ID. Can be passed multiple times. Defaults to AMAZON_MARKETPLACE_ID.",
    )
    parser.add_argument("--start-date", required=True, help="Inclusive start date, YYYY-MM-DD.")
    parser.add_argument("--end-date", required=True, help="Inclusive end date, YYYY-MM-DD.")
    parser.add_argument(
        "--chunk-days",
        type=int,
        default=30,
        help="Inclusive calendar days per request chunk. Default: 30.",
    )
    parser.add_argument(
        "--report-option",
        action="append",
        default=[],
        help="Optional reportOptions entry in KEY=VALUE form. Can be passed multiple times.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually submit requests. Default is dry-run preview only.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Submit even if a matching local manifest exists.",
    )
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=2.0,
        help="Delay between Amazon calls to reduce throttling risk. Default: 2.0.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    result = BackfillReportRequestsService(settings=settings).run(
        report_type=args.report_type,
        marketplace_ids=args.marketplace_ids,
        start_date=date.fromisoformat(args.start_date),
        end_date=date.fromisoformat(args.end_date),
        chunk_days=args.chunk_days,
        report_options=_parse_report_options(args.report_option),
        dry_run=not args.execute,
        force=args.force,
        pause_seconds=args.pause_seconds,
    )

    print(
        "SP-API backfill "
        f"status={'dry_run' if result.dry_run else 'submitted'} "
        f"total={result.total_count} created={result.created_count} "
        f"skipped_existing={result.skipped_count} failed={result.failed_count}"
    )
    for row in result.window_results:
        suffix = f" manifest={row.manifest_path}" if row.manifest_path else ""
        message = f" message={row.message}" if row.message else ""
        print(f"{row.status}: {row.report_type} {row.start_date}..{row.end_date}{suffix}{message}")
    if result.dry_run:
        print("Dry-run only. Re-run with --execute after reviewing the planned chunks.")


def _parse_report_options(values: list[str]) -> dict[str, str] | None:
    options: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"Invalid --report-option value, expected KEY=VALUE: {value}")
        key, option_value = value.split("=", 1)
        key = key.strip()
        if not key:
            raise SystemExit(f"Invalid --report-option value, empty key: {value}")
        options[key] = option_value.strip()
    return options or None


if __name__ == "__main__":
    main()
