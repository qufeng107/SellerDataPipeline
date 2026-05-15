from __future__ import annotations

import logging
from typing import Any

from seller_data_pipeline.config.settings import Settings, get_settings
from seller_data_pipeline.integrations.amazon.ads_api_client import AmazonAdsApiClient
from seller_data_pipeline.parsers.amazon.ads_report_parser import AdsReportParser
from seller_data_pipeline.sampling.ads_manifest_store import AdsManifestStore
from seller_data_pipeline.sampling.ads_raw_report_files import AdsRawReportFileStore
from seller_data_pipeline.sampling.local_manifest_store import utc_now_iso
from seller_data_pipeline.sampling.raw_report_files import decode_report_content
from seller_data_pipeline.sampling.report_analyzer import analyze_report_file
from seller_data_pipeline.sampling.schema_drift import (
    build_ads_expected_schema,
    validate_report_schema,
)

logger = logging.getLogger(__name__)

ADS_COMPLETED_STATUSES = {"COMPLETED", "SUCCESS", "DONE"}
ADS_FAILED_STATUSES = {"FAILED", "CANCELLED"}


class CollectAdsReportsService:
    """Poll local Amazon Ads report manifests and download completed reports."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        ads_api_client: AmazonAdsApiClient | None = None,
        manifest_store: AdsManifestStore | None = None,
        raw_file_store: AdsRawReportFileStore | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.ads_api_client = ads_api_client or AmazonAdsApiClient(settings=self.settings)
        self.manifest_store = manifest_store or AdsManifestStore(
            root_dir=self.settings.local_sampling_root
        )
        self.raw_file_store = raw_file_store or AdsRawReportFileStore(
            root_dir=self.settings.raw_reports_root
        )

    def run(self, *, limit: int) -> list[dict[str, Any]]:
        report_manifests = self.manifest_store.iter_collectable_report_requests(limit=limit)
        logger.info("Found %s local Amazon Ads report request(s) to check", len(report_manifests))
        results: list[dict[str, Any]] = []
        for manifest in report_manifests:
            report_id = str(manifest["ads_report_id"])
            profile_id = str(manifest["profile_id"])
            report_status = self.ads_api_client.get_report(
                profile_id=profile_id,
                report_id=report_id,
            )
            processing_status = str(report_status.get("status") or "UNKNOWN").upper()
            report_url = _extract_report_url(report_status)
            updates: dict[str, Any] = {
                "processing_status": processing_status,
                "last_checked_at_utc": utc_now_iso(),
                "amazon_ads_get_report_response": _redact_report_url(report_status),
            }
            if processing_status in ADS_COMPLETED_STATUSES:
                updates["completed_at_utc"] = utc_now_iso()
            elif processing_status in ADS_FAILED_STATUSES:
                updates["error_message"] = str(
                    report_status.get("failureReason") or processing_status
                )
            updated_manifest = self.manifest_store.update_report_request(report_id, updates)
            logger.info(
                "Checked ads_report_id=%s processing_status=%s",
                report_id,
                processing_status,
            )

            if processing_status in ADS_COMPLETED_STATUSES and report_url:
                updated_manifest = self._download_completed_report(
                    manifest=updated_manifest,
                    report_url=report_url,
                    report_status=report_status,
                )
            elif processing_status in ADS_COMPLETED_STATUSES and not report_url:
                updated_manifest = self.manifest_store.update_report_request(
                    report_id,
                    {
                        "error_message": "Amazon Ads report completed but did not include a URL",
                    },
                )
            results.append(updated_manifest)
        return results

    def _download_completed_report(
        self,
        *,
        manifest: dict[str, Any],
        report_url: str,
        report_status: dict[str, Any],
    ) -> dict[str, Any]:
        report_id = str(manifest["ads_report_id"])
        downloaded = self.ads_api_client.download_report(document_url=report_url)
        parse_status = "NOT_STARTED"
        normalized_row_count: int | None = None
        parse_error_message: str | None = None
        try:
            downloaded_text, _encoding = decode_report_content(downloaded.content)
            normalized_row_count = len(
                AdsReportParser().parse_text(
                    text=downloaded_text,
                    profile_id=str(manifest["profile_id"]),
                    report_type_id=str(manifest["report_type_id"]),
                    source_report_id=report_id,
                )
            )
            parse_status = "PARSED"
        except Exception as exc:  # noqa: BLE001 - local sampling should preserve raw file.
            logger.warning("Amazon Ads downloaded report parse failed: report_id=%s", report_id)
            parse_status = "FAILED"
            parse_error_message = str(exc)

        saved = self.raw_file_store.save_report_bytes(
            profile_id=str(manifest["profile_id"]),
            report_type_id=str(manifest["report_type_id"]),
            report_id=report_id,
            content=downloaded.content,
        )
        schema_validation = self._validate_downloaded_schema(
            manifest=manifest,
            raw_file_path=str(saved.file_path),
        )
        raw_manifest = {
            "source_system": "amazon_ads",
            "ads_report_id": report_id,
            "profile_id": manifest.get("profile_id"),
            "report_type_id": manifest.get("report_type_id"),
            "ad_product": manifest.get("ad_product"),
            "group_by": manifest.get("group_by") or [],
            "columns": manifest.get("columns") or [],
            "time_unit": manifest.get("time_unit"),
            "data_start_date": manifest.get("data_start_date"),
            "data_end_date": manifest.get("data_end_date"),
            "raw_file_path": str(saved.file_path),
            "checksum_sha256": saved.checksum_sha256,
            "size_bytes": saved.size_bytes,
            "downloaded_at_utc": utc_now_iso(),
            "amazon_ads_get_report_response": _redact_report_url(report_status),
            "download_raw_size_bytes": downloaded.raw_size_bytes,
            "download_decompressed": downloaded.decompressed,
            "parse_status": parse_status,
            "normalized_row_count": normalized_row_count,
            "parse_error_message": parse_error_message,
            "schema_validation": schema_validation,
            "preview": {
                "encoding": saved.preview.encoding,
                "file_format": saved.preview.file_format,
                "top_level_type": saved.preview.top_level_type,
                "sample_rows": saved.preview.sample_rows,
                "row_count_previewed": saved.preview.row_count_previewed,
            },
        }
        raw_manifest_path = self.manifest_store.save_raw_file_manifest(
            report_id=report_id,
            manifest=raw_manifest,
        )
        logger.info(
            "Downloaded Amazon Ads report_id=%s raw_file=%s",
            report_id,
            saved.file_path,
        )
        return self.manifest_store.update_report_request(
            report_id,
            {
                "download_status": "DOWNLOADED",
                "downloaded_at_utc": utc_now_iso(),
                "raw_file_path": str(saved.file_path),
                "raw_file_manifest_path": str(raw_manifest_path),
                "checksum_sha256": saved.checksum_sha256,
                "parse_status": parse_status,
                "normalized_row_count": normalized_row_count,
                "parse_error_message": parse_error_message,
                "schema_validation_status": schema_validation.get("status"),
                "schema_validation_severity": schema_validation.get("severity"),
                "schema_validation_requires_review": schema_validation.get("requires_review"),
                "schema_validation_message": schema_validation.get("message"),
                "error_message": None if parse_status == "PARSED" else parse_error_message,
            },
        )

    def _validate_downloaded_schema(
        self,
        *,
        manifest: dict[str, Any],
        raw_file_path: str,
    ) -> dict[str, Any]:
        report_type_id = str(manifest.get("report_type_id") or "UNKNOWN")
        try:
            analysis = analyze_report_file(
                raw_file_path=raw_file_path,
                report_type=report_type_id,
                marketplace_id=str(manifest.get("profile_id") or "UNKNOWN"),
                source_system="amazon_ads",
                redact_sample_values=True,
            )
            result = validate_report_schema(
                analysis=analysis,
                expected_schema=build_ads_expected_schema(report_type_id),
            )
            payload = result.to_dict()
            payload["requires_review"] = result.requires_review
            return payload
        except Exception as exc:  # noqa: BLE001 - raw file is already preserved for review.
            logger.warning(
                "Amazon Ads schema validation failed: report_type_id=%s raw_file_path=%s",
                report_type_id,
                raw_file_path,
            )
            return {
                "source_system": "amazon_ads",
                "report_type": report_type_id,
                "raw_file_path": raw_file_path,
                "status": "validation_failed",
                "severity": "warning",
                "requires_review": True,
                "message": str(exc),
            }


def _extract_report_url(report_status: dict[str, Any]) -> str | None:
    for key in ("url", "location", "downloadUrl"):
        value = report_status.get(key)
        if value:
            return str(value)
    return None


def _redact_report_url(report_status: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(report_status)
    for key in ("url", "location", "downloadUrl"):
        if key in redacted:
            redacted[key] = "<redacted-presigned-url>"
    return redacted
