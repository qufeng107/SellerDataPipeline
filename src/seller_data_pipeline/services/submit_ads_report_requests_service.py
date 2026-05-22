from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from seller_data_pipeline.common.date_windows import recent_days_window
from seller_data_pipeline.common.exceptions import ConfigurationError
from seller_data_pipeline.config.settings import Settings, get_settings
from seller_data_pipeline.integrations.amazon.ads_api_client import AmazonAdsApiClient
from seller_data_pipeline.sampling.ads_manifest_store import AdsManifestStore
from seller_data_pipeline.sampling.local_manifest_store import utc_now_iso

logger = logging.getLogger(__name__)


class SubmitAdsReportRequestsService:
    """Submit Amazon Ads Reporting v3 requests and persist local manifests."""

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

    def run(
        self,
        *,
        profile_id: str | None,
        report_type_id: str,
        ad_product: str,
        group_by: list[str],
        columns: list[str],
        days: int | None = 14,
        start_date: date | None = None,
        end_date: date | None = None,
        time_unit: str = "DAILY",
        name: str | None = None,
        today: date | None = None,
    ) -> Path:
        profile_id = profile_id or self.settings.amazon_ads_profile_id
        if not profile_id:
            raise ConfigurationError(
                "AMAZON_ADS_PROFILE_ID is required or pass --profile-id explicitly"
            )
        if days is not None and (start_date is not None or end_date is not None):
            raise ValueError("Pass either days or start_date/end_date, not both")
        if start_date is not None or end_date is not None:
            if start_date is None or end_date is None:
                raise ValueError("start_date and end_date must be provided together")
            if end_date < start_date:
                raise ValueError("end_date must be on or after start_date")
            window_start = start_date
            window_end = end_date
        else:
            if days is None:
                raise ValueError("days is required when start_date/end_date are not provided")
            window = recent_days_window(today=today or date.today(), days=days)
            window_start = window.start
            window_end = window.end
        report_name = name or f"SellerDataPipeline {report_type_id} {window_start} to {window_end}"
        logger.info(
            "Submitting Amazon Ads report: profile_id=%s report_type_id=%s start=%s end=%s",
            profile_id,
            report_type_id,
            window_start,
            window_end,
        )
        result = self.ads_api_client.create_report(
            profile_id=profile_id,
            name=report_name,
            start_date=window_start,
            end_date=window_end,
            ad_product=ad_product,
            report_type_id=report_type_id,
            group_by=group_by,
            columns=columns,
            time_unit=time_unit,
        )
        manifest = {
            "source_system": "amazon_ads",
            "ads_report_id": result.report_id,
            "profile_id": profile_id,
            "report_type_id": report_type_id,
            "ad_product": ad_product,
            "group_by": group_by,
            "columns": columns,
            "time_unit": time_unit,
            "data_start_date": window_start.isoformat(),
            "data_end_date": window_end.isoformat(),
            "processing_status": str(result.payload.get("status") or "SUBMITTED").upper(),
            "download_status": "NOT_STARTED",
            "parse_status": "NOT_STARTED",
            "submitted_at_utc": utc_now_iso(),
            "last_checked_at_utc": None,
            "completed_at_utc": None,
            "raw_file_path": None,
            "raw_file_manifest_path": None,
            "error_message": None,
            "amazon_ads_create_report_response": result.payload,
        }
        manifest_path = self.manifest_store.save_report_request(manifest)
        logger.info(
            "Submitted Amazon Ads report: report_id=%s manifest=%s",
            result.report_id,
            manifest_path,
        )
        return manifest_path
