from __future__ import annotations

import json
import logging
from typing import Any

from seller_data_pipeline.config.settings import Settings, get_settings
from seller_data_pipeline.integrations.amazon.sp_api_client import AmazonSpApiClient
from seller_data_pipeline.sampling.local_manifest_store import LocalManifestStore, utc_now_iso
from seller_data_pipeline.sampling.raw_report_files import RawReportFileStore

logger = logging.getLogger(__name__)

TERMINAL_REPORT_STATUSES = {"DONE", "CANCELLED", "FATAL"}


class CollectReadyReportsService:
    """Poll local sampling report manifests and download ready Amazon reports.

    DONE reports are downloaded as normal raw data files. Some FATAL reports still contain a
    reportDocumentId; those documents are diagnostic artifacts rather than usable business data,
    so they are saved separately with download_status=DIAGNOSTIC_DOWNLOADED.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        sp_api_client: AmazonSpApiClient | None = None,
        manifest_store: LocalManifestStore | None = None,
        raw_file_store: RawReportFileStore | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.sp_api_client = sp_api_client or AmazonSpApiClient(settings=self.settings)
        self.manifest_store = manifest_store or LocalManifestStore(
            root_dir=self.settings.local_sampling_root
        )
        self.raw_file_store = raw_file_store or RawReportFileStore(
            root_dir=self.settings.raw_reports_root
        )

    def run(self, *, limit: int) -> list[dict[str, Any]]:
        report_manifests = self.manifest_store.iter_collectable_report_requests(limit=limit)
        logger.info("Found %s local report request(s) to check", len(report_manifests))

        results: list[dict[str, Any]] = []
        for manifest in report_manifests:
            report_id = str(manifest["report_id"])
            try:
                results.append(self._collect_one(manifest))
            except Exception as exc:
                logger.exception("Failed to collect Amazon report: report_id=%s", report_id)
                updated = self.manifest_store.update_report_request(
                    report_id,
                    {
                        "last_checked_at_utc": utc_now_iso(),
                        "error_message": str(exc),
                    },
                )
                results.append(updated)
        return results

    def _collect_one(self, manifest: dict[str, Any]) -> dict[str, Any]:
        report_id = str(manifest["report_id"])
        report_payload = self.sp_api_client.get_report(report_id=report_id)
        report_status = _extract_report_status(report_payload)
        report_document_id = _extract_report_document_id(report_payload)

        updates: dict[str, Any] = {
            "processing_status": report_status,
            "last_checked_at_utc": utc_now_iso(),
            "amazon_get_report_response": report_payload,
        }
        if report_document_id:
            updates["report_document_id"] = report_document_id
        if report_status in TERMINAL_REPORT_STATUSES:
            updates["completed_at_utc"] = utc_now_iso()
        if report_status == "FATAL":
            updates["error_message"] = _extract_report_error_message(report_payload) or "FATAL"
        if report_status == "CANCELLED":
            updates["error_message"] = "CANCELLED"

        manifest = self.manifest_store.update_report_request(report_id, updates)
        logger.info("Checked report_id=%s processing_status=%s", report_id, report_status)

        document_id = str(manifest.get("report_document_id") or report_document_id or "")
        if report_status == "DONE":
            if not document_id:
                return self.manifest_store.update_report_request(
                    report_id,
                    {"error_message": "DONE report did not contain reportDocumentId"},
                )
            return self._download_report_document(
                manifest=manifest,
                report_document_id=document_id,
                diagnostic=False,
            )

        if report_status == "FATAL" and document_id:
            return self._download_report_document(
                manifest=manifest,
                report_document_id=document_id,
                diagnostic=True,
            )

        return manifest

    def _download_report_document(
        self,
        *,
        manifest: dict[str, Any],
        report_document_id: str,
        diagnostic: bool,
    ) -> dict[str, Any]:
        report_id = str(manifest["report_id"])
        document_info = self.sp_api_client.get_report_document(
            report_document_id=report_document_id,
        )
        document_url = str(document_info.get("url") or "")
        compression_algorithm = document_info.get("compressionAlgorithm")
        downloaded = self.sp_api_client.download_report_document(
            document_url=document_url,
            compression_algorithm=str(compression_algorithm) if compression_algorithm else None,
        )

        saved = self.raw_file_store.save_report_bytes(
            report_type=str(manifest["report_type"]),
            marketplace_ids=list(manifest.get("marketplace_ids") or []),
            report_id=report_id,
            content=downloaded.content,
        )
        raw_manifest = {
            "report_id": report_id,
            "report_type": manifest["report_type"],
            "marketplace_ids": manifest.get("marketplace_ids") or [],
            "report_document_id": report_document_id,
            "raw_file_path": str(saved.file_path),
            "checksum_sha256": saved.checksum_sha256,
            "size_bytes": saved.size_bytes,
            "downloaded_at_utc": utc_now_iso(),
            "is_diagnostic_document": diagnostic,
            "amazon_get_report_document_response": _redact_document_url(document_info),
            "compression_algorithm": downloaded.compression_algorithm,
            "download_raw_size_bytes": downloaded.raw_size_bytes,
            "download_decompressed": downloaded.decompressed,
            "preview": {
                "encoding": saved.preview.encoding,
                "delimiter": saved.preview.delimiter,
                "header": saved.preview.header,
                "sample_rows": saved.preview.sample_rows,
                "row_count_previewed": saved.preview.row_count_previewed,
            },
        }
        raw_manifest_path = self.manifest_store.save_raw_file_manifest(
            report_id=report_id,
            manifest=raw_manifest,
        )
        logger.info(
            "Downloaded %sreport_id=%s document=%s raw_file=%s",
            "diagnostic " if diagnostic else "",
            report_id,
            report_document_id,
            saved.file_path,
        )

        if diagnostic:
            diagnostic_message = _extract_diagnostic_document_message(downloaded.content)
            return self.manifest_store.update_report_request(
                report_id,
                {
                    "download_status": "DIAGNOSTIC_DOWNLOADED",
                    "diagnostic_downloaded_at_utc": utc_now_iso(),
                    "raw_file_path": None,
                    "raw_file_manifest_path": None,
                    "diagnostic_file_path": str(saved.file_path),
                    "diagnostic_file_manifest_path": str(raw_manifest_path),
                    "diagnostic_checksum_sha256": saved.checksum_sha256,
                    "diagnostic_error_message": diagnostic_message,
                    "amazon_get_report_document_response": _redact_document_url(document_info),
                    "error_message": diagnostic_message or "FATAL diagnostic document downloaded",
                },
            )

        return self.manifest_store.update_report_request(
            report_id,
            {
                "download_status": "DOWNLOADED",
                "downloaded_at_utc": utc_now_iso(),
                "raw_file_path": str(saved.file_path),
                "raw_file_manifest_path": str(raw_manifest_path),
                "checksum_sha256": saved.checksum_sha256,
                "amazon_get_report_document_response": _redact_document_url(document_info),
                "error_message": None,
            },
        )


def _payload_dict(payload: dict[str, Any]) -> dict[str, Any]:
    nested = payload.get("payload")
    return nested if isinstance(nested, dict) else {}


def _extract_report_status(payload: dict[str, Any]) -> str:
    value = payload.get("processingStatus") or _payload_dict(payload).get("processingStatus")
    return str(value or "UNKNOWN")


def _extract_report_document_id(payload: dict[str, Any]) -> str | None:
    value = payload.get("reportDocumentId") or _payload_dict(payload).get("reportDocumentId")
    return str(value) if value else None


def _extract_report_error_message(payload: dict[str, Any]) -> str | None:
    value = payload.get("processingStatus") or _payload_dict(payload).get("processingStatus")
    return str(value) if value else None


def _extract_diagnostic_document_message(content: bytes) -> str | None:
    text = _decode_diagnostic_content(content).strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text[:1000]
    if isinstance(payload, dict):
        for key in ("reportRequestError", "message", "error", "errorMessage"):
            value = payload.get(key)
            if value:
                return str(value)
    return text[:1000]


def _decode_diagnostic_content(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _redact_document_url(document_info: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(document_info)
    if "url" in redacted:
        redacted["url"] = "<redacted-presigned-url>"
    return redacted
