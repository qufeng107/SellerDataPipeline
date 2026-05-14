from __future__ import annotations

import argparse

from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.integrations.amazon.report_types import LISTINGS_ALL_DATA
from seller_data_pipeline.jobs.submit_report_requests_job import run


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Submit Amazon report requests in local sampling mode."
    )
    parser.add_argument(
        "--report-type",
        default=LISTINGS_ALL_DATA,
        help="Amazon report type to request. Default: GET_MERCHANT_LISTINGS_ALL_DATA.",
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
        default=None,
        help="Optional lookback window. Omit for report types that do not need date ranges.",
    )
    parser.add_argument(
        "--report-option",
        action="append",
        default=[],
        help=(
            "Optional Amazon reportOptions entry in KEY=VALUE form. "
            "Can be passed multiple times."
        ),
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    manifest_path = run(
        report_type=args.report_type,
        marketplace_ids=args.marketplace_ids,
        days=args.days,
        report_options=_parse_report_options(args.report_option),
    )
    print(f"Submitted report request. Manifest: {manifest_path}")


def _parse_report_options(values: list[str]) -> dict[str, str]:
    options: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"Invalid --report-option value, expected KEY=VALUE: {value}")
        key, option_value = value.split("=", 1)
        key = key.strip()
        if not key:
            raise SystemExit(f"Invalid --report-option value, empty key: {value}")
        options[key] = option_value.strip()
    return options


if __name__ == "__main__":
    main()
