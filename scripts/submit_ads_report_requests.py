from __future__ import annotations

import argparse

from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.services.submit_ads_report_requests_service import (
    SubmitAdsReportRequestsService,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Submit one Amazon Ads Reporting v3 request in local sampling mode."
    )
    parser.add_argument(
        "--profile-id",
        help="Amazon Ads profile ID. Defaults to AMAZON_ADS_PROFILE_ID.",
    )
    parser.add_argument("--report-type-id", required=True, help="Example: spCampaigns")
    parser.add_argument("--ad-product", default="SPONSORED_PRODUCTS")
    parser.add_argument(
        "--group-by",
        action="append",
        required=True,
        help="Can be passed multiple times.",
    )
    parser.add_argument(
        "--column",
        action="append",
        required=True,
        help="Can be passed multiple times.",
    )
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--time-unit", default="DAILY", choices=["DAILY", "SUMMARY"])
    parser.add_argument("--name", help="Optional report name.")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    path = SubmitAdsReportRequestsService(settings=settings).run(
        profile_id=args.profile_id,
        report_type_id=args.report_type_id,
        ad_product=args.ad_product,
        group_by=args.group_by,
        columns=args.column,
        days=args.days,
        time_unit=args.time_unit,
        name=args.name,
    )
    print(f"Submitted Amazon Ads report request. Manifest: {path}")


if __name__ == "__main__":
    main()
