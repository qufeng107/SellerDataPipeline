from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from seller_data_pipeline.common.exceptions import ConfigurationError
from seller_data_pipeline.config.settings import Settings, get_settings
from seller_data_pipeline.integrations.amazon.report_types import SETTLEMENT_V2
from seller_data_pipeline.integrations.amazon.sp_api_client import AmazonSpApiClient
from seller_data_pipeline.sampling.local_manifest_store import LocalManifestStore, utc_now_iso

logger = logging.getLogger(__name__)

SAFE_REPORT_DISCOVERY_LOOKBACK_DAYS = 89


class DiscoverAvailableReportsService:
    """Discover Amazon-generated reports and save them as local sampling manifests."""

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
        report_type: str = SETTLEMENT_V2,
        marketplace_ids: list[str] | None = None,
        days: int | None = SAFE_REPORT_DISCOVERY_LOOKBACK_DAYS,
        page_size: int = 20,
        max_pages: int = 3,
        today: date | None = None,
    ) -> list[Path]:
        """Discover existing DONE reports and write local manifests for collection."""

        if page_size <= 0 or page_size > 100:
            raise ValueError("page_size must be between 1 and 100")
        if max_pages <= 0:
            raise ValueError("max_pages must be positive")

        marketplace_ids = marketplace_ids or self._default_marketplace_ids()
        created_since, created_until = self._build_created_window_datetimes(
            days=days,
            today=today,
        )

        logger.info(
            "Discovering Amazon reports: report_type=%s marketplace_ids=%s "
            "created_since=%s created_until=%s",
            report_type,
            marketplace_ids,
            created_since,
            created_until,
        )

        manifest_paths: list[Path] = []
        next_token: str | None = None
        for page_number in range(1, max_pages + 1):
            payload = self.sp_api_client.get_reports(
                report_types=[report_type],
                processing_statuses=["DONE"],
                marketplace_ids=marketplace_ids,
                page_size=page_size,
                created_since=created_since,
                created_until=created_until,
                next_token=next_token,
            )
            reports = _extract_reports(payload)
            logger.info(
                "Discovered %s report(s) on page %s for report_type=%s",
                len(reports),
                page_number,
                report_type,
            )
            for report in reports:
                manifest_paths.append(
                    self._save_discovered_report_manifest(
                        report=report,
                        requested_report_type=report_type,
                        requested_marketplace_ids=marketplace_ids,
                    )
                )

            next_token = _extract_next_token(payload)
            if not next_token:
                break

        return manifest_paths

    def _save_discovered_report_manifest(
        self,
        *,
        report: dict[str, Any],
        requested_report_type: str,
        requested_marketplace_ids: list[str],
    ) -> Path:
        report_id = str(report.get("reportId") or "")
        if not report_id:
            raise ValueError(f"Discovered report did not contain reportId: {report!r}")

        report_type = str(report.get("reportType") or requested_report_type)
        response_marketplace_ids = _as_string_list(report.get("marketplaceIds"))
        marketplace_ids = response_marketplace_ids or requested_marketplace_ids
        marketplace_ids_source = (
            "amazon_response" if response_marketplace_ids else "request_filter_fallback_unverified"
        )
        processing_status = str(report.get("processingStatus") or "DONE")
        report_document_id = report.get("reportDocumentId")

        manifest_path = self.manifest_store.report_request_path(report_id)
        if manifest_path.exists():
            existing = self.manifest_store.read_report_request(report_id)
            if existing.get("download_status") == "DOWNLOADED":
                logger.info(
                    "Keeping existing downloaded discovered report manifest: "
                    "report_id=%s manifest=%s",
                    report_id,
                    manifest_path,
                )
                return manifest_path

            updated = dict(existing)
            updated.update(
                {
                    "report_type": report_type,
                    "marketplace_ids": marketplace_ids,
                    "marketplace_ids_source": marketplace_ids_source,
                    "response_marketplace_ids": response_marketplace_ids,
                    "data_start_time": report.get("dataStartTime"),
                    "data_end_time": report.get("dataEndTime"),
                    "created_time": report.get("createdTime"),
                    "processing_status": processing_status,
                    "completed_at_utc": report.get("processingEndTime") or utc_now_iso(),
                    "report_document_id": str(report_document_id) if report_document_id else None,
                    "discovered_at_utc": utc_now_iso(),
                    "amazon_get_reports_response_item": report,
                }
            )
            manifest_path = self.manifest_store.save_report_request(updated)
            logger.info(
                "Updated existing discovered Amazon report manifest: report_id=%s manifest=%s",
                report_id,
                manifest_path,
            )
            return manifest_path

        manifest = {
            "report_id": report_id,
            "report_type": report_type,
            "marketplace_ids": marketplace_ids,
            "marketplace_ids_source": marketplace_ids_source,
            "response_marketplace_ids": response_marketplace_ids,
            "data_start_time": report.get("dataStartTime"),
            "data_end_time": report.get("dataEndTime"),
            "created_time": report.get("createdTime"),
            "processing_status": processing_status,
            "download_status": "NOT_STARTED",
            "parse_status": "NOT_STARTED",
            "submitted_at_utc": None,
            "discovered_at_utc": utc_now_iso(),
            "last_checked_at_utc": None,
            "completed_at_utc": report.get("processingEndTime") or utc_now_iso(),
            "report_document_id": str(report_document_id) if report_document_id else None,
            "raw_file_path": None,
            "raw_file_manifest_path": None,
            "error_message": None,
            "amazon_get_reports_response_item": report,
        }
        manifest_path = self.manifest_store.save_report_request(manifest)
        logger.info(
            "Saved discovered Amazon report manifest: report_id=%s manifest=%s",
            report_id,
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
    def _normalize_lookback_days(days: int) -> int:
        if days <= 0:
            raise ValueError("days must be positive")
        if days > SAFE_REPORT_DISCOVERY_LOOKBACK_DAYS:
            logger.warning(
                "Requested report discovery lookback days=%s exceeds the safe limit %s. "
                "Using %s days to avoid Amazon getReports 90-day boundary errors.",
                days,
                SAFE_REPORT_DISCOVERY_LOOKBACK_DAYS,
                SAFE_REPORT_DISCOVERY_LOOKBACK_DAYS,
            )
            return SAFE_REPORT_DISCOVERY_LOOKBACK_DAYS
        return days

    @classmethod
    def _build_created_window_datetimes(
        cls,
        *,
        days: int | None,
        today: date | None,
    ) -> tuple[datetime | None, datetime | None]:
        if days is None:
            return None, None

        normalized_days = cls._normalize_lookback_days(days)
        if today is not None:
            created_until = datetime.combine(today, datetime.max.time(), tzinfo=UTC)
        else:
            created_until = datetime.now(UTC)
        created_since = created_until - timedelta(days=normalized_days)
        return created_since, created_until


def _extract_reports(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidate = payload.get("reports")
    if candidate is None and isinstance(payload.get("payload"), dict):
        candidate = payload["payload"].get("reports")
    if candidate is None and isinstance(payload.get("payload"), list):
        candidate = payload.get("payload")
    if not isinstance(candidate, list):
        return []
    return [item for item in candidate if isinstance(item, dict)]


def _extract_next_token(payload: dict[str, Any]) -> str | None:
    value = payload.get("nextToken")
    if value is None and isinstance(payload.get("payload"), dict):
        value = payload["payload"].get("nextToken")
    return str(value) if value else None


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item]
