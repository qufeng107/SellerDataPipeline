from __future__ import annotations

import argparse

from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.jobs.generate_periodic_reports_job import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate periodic seller reports.")
    parser.add_argument(
        "--type",
        choices=["weekly", "monthly", "quarterly"],
        default="weekly",
        help="Report type to generate.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    run(report_type=args.type)


if __name__ == "__main__":
    main()
