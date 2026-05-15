from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.integrations.amazon.ads_api_client import AmazonAdsApiClient


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Test Amazon Ads API credentials by exchanging the refresh token and listing profiles. "
            "This command is read-only and does not submit report requests."
        )
    )
    parser.add_argument(
        "--profile-id",
        default=None,
        help="Optional profile ID to validate. Defaults to AMAZON_ADS_PROFILE_ID when set.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a readable summary.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    result = AmazonAdsApiClient(settings=settings).check_connection(profile_id=args.profile_id)
    payload = asdict(result)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return

    print("Amazon Ads API connection check passed.")
    print(f"endpoint={payload['api_endpoint']}")
    print(f"lwa_access_token_obtained={payload['lwa_access_token_obtained']}")
    print(f"token_type={payload['token_type']} expires_in={payload['token_expires_in']}")
    print(f"profile_count={payload['profile_count']}")
    selected_profile_id = payload.get("selected_profile_id")
    if selected_profile_id:
        print(
            "selected_profile_id={selected_profile_id} found={selected_profile_found}".format(
                selected_profile_id=selected_profile_id,
                selected_profile_found=payload.get("selected_profile_found"),
            )
        )
    print("")
    print("Available profiles:")
    for profile in payload["profiles"]:
        account_info = profile.get("accountInfo") or {}
        print(
            "profile_id={profile_id} country={country} currency={currency} "
            "timezone={timezone} account_type={account_type} account_name={account_name} "
            "valid_payment={valid_payment}".format(
                profile_id=profile.get("profileId"),
                country=profile.get("countryCode"),
                currency=profile.get("currencyCode"),
                timezone=profile.get("timezone"),
                account_type=account_info.get("type"),
                account_name=account_info.get("name"),
                valid_payment=account_info.get("validPaymentMethod"),
            )
        )
    recommended_profile_id = _select_recommended_profile(payload)
    if recommended_profile_id:
        print("")
        print("Next step example:")
        print(f"AMAZON_ADS_PROFILE_ID='{recommended_profile_id}'")


def _select_recommended_profile(payload: dict) -> str | None:
    selected_profile_id = payload.get("selected_profile_id")
    if selected_profile_id and payload.get("selected_profile_found"):
        return str(selected_profile_id)

    profiles = list(payload.get("profiles") or [])
    for profile in profiles:
        account_info = profile.get("accountInfo") or {}
        if (
            profile.get("countryCode") == "US"
            and profile.get("currencyCode") == "USD"
            and account_info.get("type") == "seller"
            and account_info.get("validPaymentMethod") is True
        ):
            return str(profile.get("profileId"))

    for profile in profiles:
        account_info = profile.get("accountInfo") or {}
        if account_info.get("type") == "seller" and account_info.get("validPaymentMethod") is True:
            return str(profile.get("profileId"))

    if profiles:
        profile_id = profiles[0].get("profileId")
        return str(profile_id) if profile_id is not None else None
    return None


if __name__ == "__main__":
    main()
