from __future__ import annotations

import argparse

from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill historical seller data.")
    parser.add_argument("--start", required=True, help="Start date, YYYY-MM-DD.")
    parser.add_argument("--end", required=True, help="End date, YYYY-MM-DD.")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    # TODO: implement backfill orchestration.
    print(f"Backfill placeholder: {args.start} to {args.end}")


if __name__ == "__main__":
    main()
