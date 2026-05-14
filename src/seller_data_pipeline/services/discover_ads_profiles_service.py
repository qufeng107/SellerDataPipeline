from __future__ import annotations

import logging
from pathlib import Path

from seller_data_pipeline.config.settings import Settings, get_settings
from seller_data_pipeline.integrations.amazon.ads_api_client import AmazonAdsApiClient
from seller_data_pipeline.sampling.ads_manifest_store import AdsManifestStore

logger = logging.getLogger(__name__)


class DiscoverAdsProfilesService:
    """Discover Amazon Ads profiles and save a local sampling manifest."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        ads_api_client: AmazonAdsApiClient | None = None,
        manifest_store: AdsManifestStore | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.ads_api_client = ads_api_client or AmazonAdsApiClient(settings=self.settings)
        self.manifest_store = manifest_store or AdsManifestStore(
            root_dir=self.settings.local_sampling_root
        )

    def run(self) -> Path:
        profiles = self.ads_api_client.list_profiles()
        manifest_path = self.manifest_store.save_profiles(profiles)
        logger.info(
            "Discovered %s Amazon Ads profile(s): manifest=%s",
            len(profiles),
            manifest_path,
        )
        return manifest_path
