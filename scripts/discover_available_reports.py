from __future__ import annotations

import argparse

from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.integrations.amazon.report_types import SETTLEMENT_V2
from seller_data_pipeline.services.discover_available_reports_service import (
    SAFE_REPORT_DISCOVERY_LOOKBACK_DAYS,
)
from seller_data_pipeline.jobs.discover_available_reports_job import run


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Discover Amazon-generated reports in local sampling mode. "
            "Use this for report types such as settlement reports that cannot be requested."
        )
    )
    parser.add_argument(
        "--report-type",
        default=SETTLEMENT_V2,
        help="Amazon report type to discover. Default: GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2.",
    )
    parser.add_argument(
        "--marketplace-id",
        action="append",
        dest="marketplace_ids",
        help=(
            "Amazon marketplace ID. Can be passed multiple times. "
            "Defaults to AMAZON_MARKETPLACE_ID."
        ),
    )
    parser.add_argument(
        "--days",
        type=int,
        default=SAFE_REPORT_DISCOVERY_LOOKBACK_DAYS,
        help=(
            "Lookback window by report creation time. "
            f"Default: {SAFE_REPORT_DISCOVERY_LOOKBACK_DAYS}. "
            "Values above this are capped to avoid Amazon getReports 90-day boundary errors."
        ),
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=20,
        help="Reports API page size, 1-100. Default: 20.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=3,
        help="Maximum pages to scan. Default: 3.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    manifest_paths = run(
        report_type=args.report_type,
        marketplace_ids=args.marketplace_ids,
        days=args.days,
        page_size=args.page_size,
        max_pages=args.max_pages,
    )
    print(f"Discovered {len(manifest_paths)} report(s).")
    for manifest_path in manifest_paths:
        print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
