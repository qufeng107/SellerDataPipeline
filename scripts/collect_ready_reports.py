from __future__ import annotations

import argparse

from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.jobs.collect_ready_reports_job import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect ready Amazon reports.")
    parser.add_argument("--limit", type=int, default=20, help="Max pending reports to check.")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    run(limit=args.limit)


if __name__ == "__main__":
    main()
