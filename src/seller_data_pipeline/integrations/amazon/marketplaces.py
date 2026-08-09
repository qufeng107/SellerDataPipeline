from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AmazonMarketplaceMetadata:
    marketplace_id: str
    country_code: str
    currency: str
    marketplace_names: tuple[str, ...] = ()


# Keep this list intentionally conservative. Add a marketplace only after its
# settlement currency/name contract has been verified against real SP-API data.
_MARKETPLACES: dict[str, AmazonMarketplaceMetadata] = {
    "ATVPDKIKX0DER": AmazonMarketplaceMetadata(
        marketplace_id="ATVPDKIKX0DER",
        country_code="US",
        currency="USD",
        marketplace_names=("Amazon.com",),
    ),
}


def get_marketplace_metadata(marketplace_id: str) -> AmazonMarketplaceMetadata | None:
    return _MARKETPLACES.get(str(marketplace_id or "").strip())


def expected_marketplace_currency(marketplace_id: str) -> str | None:
    metadata = get_marketplace_metadata(marketplace_id)
    return metadata.currency if metadata else None


def expected_marketplace_names(marketplace_id: str) -> tuple[str, ...]:
    metadata = get_marketplace_metadata(marketplace_id)
    return metadata.marketplace_names if metadata else ()


__all__ = [
    "AmazonMarketplaceMetadata",
    "expected_marketplace_currency",
    "expected_marketplace_names",
    "get_marketplace_metadata",
]
