from __future__ import annotations

import argparse

from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.jobs.submit_report_requests_job import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit Amazon report requests.")
    parser.add_argument("--days", type=int, default=45, help="Lookback days for report requests.")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    run(days=args.days)


if __name__ == "__main__":
    main()
