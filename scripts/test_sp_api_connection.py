from __future__ import annotations

import argparse
import json
import logging
from typing import Any

from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.integrations.amazon.sp_api_client import AmazonSpApiClient

logger = logging.getLogger(__name__)


def _extract_marketplaces(payload: dict[str, Any]) -> list[dict[str, Any]]:
    marketplaces: list[dict[str, Any]] = []
    for item in payload.get("payload", []):
        marketplace = item.get("marketplace", {}) if isinstance(item, dict) else {}
        if isinstance(marketplace, dict):
            marketplaces.append(marketplace)
    return marketplaces


def main() -> None:
    parser = argparse.ArgumentParser(description="Test Amazon SP-API authentication and access.")
    parser.add_argument(
        "--show-raw",
        action="store_true",
        help="Print the full marketplaceParticipations JSON response.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    client = AmazonSpApiClient(settings=settings)
    payload = client.get_marketplace_participations()

    marketplaces = _extract_marketplaces(payload)
    logger.info("SP-API connection test succeeded. Marketplaces returned: %s", len(marketplaces))

    if args.show_raw:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    print("SP-API connection test succeeded.")
    print("Marketplace participations:")
    for marketplace in marketplaces:
        marketplace_id = marketplace.get("id", "")
        name = marketplace.get("name", "")
        country_code = marketplace.get("countryCode", "")
        default_currency = marketplace.get("defaultCurrencyCode", "")
        print(f"- {marketplace_id} | {name} | {country_code} | {default_currency}")


if __name__ == "__main__":
    main()
