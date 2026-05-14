from __future__ import annotations

from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.services.discover_ads_profiles_service import DiscoverAdsProfilesService


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    service = DiscoverAdsProfilesService(settings=settings)
    manifest_path = service.run()
    print(f"Saved Amazon Ads profiles manifest: {manifest_path}")

    profiles = service.manifest_store.read_profiles()
    for profile in profiles:
        print(
            "profile_id={profile_id} country_code={country_code} currency={currency} "
            "account_name={account_name} account_id={account_id}".format(
                profile_id=profile.get("profileId") or profile.get("profile_id"),
                country_code=profile.get("countryCode"),
                currency=profile.get("currencyCode"),
                account_name=_account_name(profile),
                account_id=_account_id(profile),
            )
        )


def _account_name(profile: dict[str, object]) -> object:
    account_info = profile.get("accountInfo")
    if isinstance(account_info, dict):
        return account_info.get("name")
    return None


def _account_id(profile: dict[str, object]) -> object:
    account_info = profile.get("accountInfo")
    if isinstance(account_info, dict):
        return account_info.get("id")
    return None


if __name__ == "__main__":
    main()
