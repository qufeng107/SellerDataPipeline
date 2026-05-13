from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time
from pathlib import Path

from seller_data_pipeline.common.date_windows import recent_days_window
from seller_data_pipeline.common.exceptions import ConfigurationError
from seller_data_pipeline.config.settings import Settings, get_settings
from seller_data_pipeline.integrations.amazon.report_types import LISTINGS_ALL_DATA
from seller_data_pipeline.integrations.amazon.sp_api_client import AmazonSpApiClient
from seller_data_pipeline.sampling.local_manifest_store import LocalManifestStore, utc_now_iso

logger = logging.getLogger(__name__)


class SubmitReportRequestsService:
    """Submit Amazon report requests and persist local sampling manifests."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        sp_api_client: AmazonSpApiClient | None = None,
        manifest_store: LocalManifestStore | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.sp_api_client = sp_api_client or AmazonSpApiClient(settings=self.settings)
        self.manifest_store = manifest_store or LocalManifestStore(
            root_dir=self.settings.local_sampling_root
        )

    def run(
        self,
        *,
        report_type: str = LISTINGS_ALL_DATA,
        marketplace_ids: list[str] | None = None,
        days: int | None = None,
        today: date | None = None,
    ) -> Path:
        marketplace_ids = marketplace_ids or self._default_marketplace_ids()
        data_start_time, data_end_time = self._build_date_window_datetimes(days=days, today=today)

        logger.info(
            "Submitting Amazon report request: report_type=%s marketplace_ids=%s start=%s end=%s",
            report_type,
            marketplace_ids,
            data_start_time,
            data_end_time,
        )
        result = self.sp_api_client.create_report(
            report_type=report_type,
            marketplace_ids=marketplace_ids,
            data_start_time=data_start_time,
            data_end_time=data_end_time,
        )

        manifest = {
            "report_id": result.report_id,
            "report_type": report_type,
            "marketplace_ids": marketplace_ids,
            "data_start_time": _dt_to_iso(data_start_time),
            "data_end_time": _dt_to_iso(data_end_time),
            "processing_status": "SUBMITTED",
            "download_status": "NOT_STARTED",
            "parse_status": "NOT_STARTED",
            "submitted_at_utc": utc_now_iso(),
            "last_checked_at_utc": None,
            "completed_at_utc": None,
            "report_document_id": None,
            "raw_file_path": None,
            "raw_file_manifest_path": None,
            "error_message": None,
            "amazon_create_report_response": result.payload,
        }
        manifest_path = self.manifest_store.save_report_request(manifest)
        logger.info(
            "Submitted Amazon report request: report_id=%s manifest=%s",
            result.report_id,
            manifest_path,
        )
        return manifest_path

    def _default_marketplace_ids(self) -> list[str]:
        if not self.settings.amazon_marketplace_id:
            raise ConfigurationError(
                "AMAZON_MARKETPLACE_ID is required or pass --marketplace-id explicitly"
            )
        return [self.settings.amazon_marketplace_id]

    @staticmethod
    def _build_date_window_datetimes(
        *,
        days: int | None,
        today: date | None,
    ) -> tuple[datetime | None, datetime | None]:
        if days is None:
            return None, None
        today = today or date.today()
        window = recent_days_window(today=today, days=days)
        return (
            datetime.combine(window.start, time.min, tzinfo=UTC),
            datetime.combine(window.end, time.min, tzinfo=UTC),
        )


def _dt_to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
