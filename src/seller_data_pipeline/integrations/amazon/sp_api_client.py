from __future__ import annotations

import gzip
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Any

import requests

from seller_data_pipeline.common.exceptions import ConfigurationError, ExternalServiceError
from seller_data_pipeline.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

REPORTS_API_VERSION = "2021-06-30"


@dataclass(frozen=True)
class LwaAccessToken:
    access_token: str
    token_type: str
    expires_in: int


@dataclass(frozen=True)
class ReportRequestResult:
    report_id: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class DownloadedReportDocument:
    content: bytes
    compression_algorithm: str | None
    raw_size_bytes: int
    decompressed: bool


class AmazonSpApiClient:
    """Small HTTP client for Amazon SP-API."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        session: requests.Session | None = None,
        timeout_seconds: int = 30,
    ) -> None:
        self.settings = settings or get_settings()
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds
        self._cached_token: LwaAccessToken | None = None
        self._cached_token_expires_at = 0.0

    def get_lwa_access_token(self) -> LwaAccessToken:
        """Exchange the stored LWA refresh token for a short-lived access token."""

        if self._cached_token and monotonic() < self._cached_token_expires_at:
            return self._cached_token

        self._validate_lwa_settings()
        response = self.session.post(
            self.settings.amazon_lwa_token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.settings.amazon_sp_api_refresh_token,
                "client_id": self.settings.amazon_lwa_client_id,
                "client_secret": self.settings.amazon_lwa_client_secret,
            },
            timeout=self.timeout_seconds,
        )
        payload = self._parse_json_response(response, context="request LWA access token")

        try:
            token = LwaAccessToken(
                access_token=str(payload["access_token"]),
                token_type=str(payload.get("token_type", "bearer")),
                expires_in=int(payload.get("expires_in", 3600)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ExternalServiceError("LWA token response did not contain a valid token") from exc

        self._cached_token = token
        self._cached_token_expires_at = monotonic() + max(token.expires_in - 60, 60)
        return token

    def get_marketplace_participations(self) -> dict[str, Any]:
        """Return marketplace participation data for the authorized seller account."""

        return self._request_json("GET", "/sellers/v1/marketplaceParticipations")

    def create_report(
        self,
        *,
        report_type: str,
        marketplace_ids: list[str],
        data_start_time: datetime | None = None,
        data_end_time: datetime | None = None,
        report_options: dict[str, str] | None = None,
    ) -> ReportRequestResult:
        """Create an Amazon report request and return Amazon's reportId."""

        if not report_type:
            raise ValueError("report_type is required")
        if not marketplace_ids:
            raise ValueError("marketplace_ids must contain at least one marketplace")

        body: dict[str, Any] = {"reportType": report_type, "marketplaceIds": marketplace_ids}
        if data_start_time is not None:
            body["dataStartTime"] = _format_sp_api_datetime(data_start_time)
        if data_end_time is not None:
            body["dataEndTime"] = _format_sp_api_datetime(data_end_time)
        if report_options:
            body["reportOptions"] = report_options

        payload = self._request_json(
            "POST",
            f"/reports/{REPORTS_API_VERSION}/reports",
            json_body=body,
        )
        payload_obj = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        report_id = str(payload.get("reportId") or payload_obj.get("reportId") or "")
        if not report_id:
            raise ExternalServiceError("createReport response did not contain reportId")
        return ReportRequestResult(report_id=report_id, payload=payload)

    def get_reports(
        self,
        *,
        report_types: list[str],
        processing_statuses: list[str] | None = None,
        marketplace_ids: list[str] | None = None,
        page_size: int | None = None,
        created_since: datetime | None = None,
        created_until: datetime | None = None,
        next_token: str | None = None,
    ) -> dict[str, Any]:
        """Return reports matching filters via the Reports API getReports operation."""

        if next_token:
            return self._request_json(
                "GET",
                f"/reports/{REPORTS_API_VERSION}/reports",
                params={"nextToken": next_token},
            )
        if not report_types:
            raise ValueError("report_types must contain at least one report type")

        params: dict[str, Any] = {"reportTypes": report_types}
        if processing_statuses:
            params["processingStatuses"] = processing_statuses
        if marketplace_ids:
            params["marketplaceIds"] = marketplace_ids
        if page_size is not None:
            params["pageSize"] = page_size
        if created_since is not None:
            params["createdSince"] = _format_sp_api_datetime(created_since)
        if created_until is not None:
            params["createdUntil"] = _format_sp_api_datetime(created_until)

        return self._request_json(
            "GET",
            f"/reports/{REPORTS_API_VERSION}/reports",
            params=params,
        )

    def get_report(self, *, report_id: str) -> dict[str, Any]:
        """Return the latest processing status for an Amazon report request."""

        if not report_id:
            raise ValueError("report_id is required")
        return self._request_json("GET", f"/reports/{REPORTS_API_VERSION}/reports/{report_id}")

    def get_report_document(self, *, report_document_id: str) -> dict[str, Any]:
        """Return the pre-signed report document URL and optional compression metadata."""

        if not report_document_id:
            raise ValueError("report_document_id is required")
        return self._request_json(
            "GET",
            f"/reports/{REPORTS_API_VERSION}/documents/{report_document_id}",
        )

    def download_report_document(
        self,
        *,
        document_url: str,
        compression_algorithm: str | None = None,
    ) -> DownloadedReportDocument:
        """Download a report document from Amazon's pre-signed document URL."""

        if not document_url:
            raise ValueError("document_url is required")

        response = self.session.get(document_url, timeout=self.timeout_seconds)
        if not 200 <= response.status_code < 300:
            message = response.text[:1000] if response.text else ""
            raise ExternalServiceError(
                "Failed to download report document: "
                f"HTTP {response.status_code}. Response: {message}"
            )

        raw_content = response.content
        compression = compression_algorithm.upper() if compression_algorithm else None
        if compression == "GZIP":
            try:
                return DownloadedReportDocument(
                    content=gzip.decompress(raw_content),
                    compression_algorithm=compression_algorithm,
                    raw_size_bytes=len(raw_content),
                    decompressed=True,
                )
            except OSError:
                logger.warning("Report document declared GZIP but content was not gzipped")

        return DownloadedReportDocument(
            content=raw_content,
            compression_algorithm=compression_algorithm,
            raw_size_bytes=len(raw_content),
            decompressed=False,
        )

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        token = self.get_lwa_access_token()
        url = f"{self.settings.amazon_sp_api_endpoint.rstrip('/')}/{path.lstrip('/')}"
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "user-agent": self.settings.amazon_sp_api_user_agent,
            "x-amz-access-token": token.access_token,
            "x-amz-date": datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
        }
        response = self.session.request(
            method=method,
            url=url,
            params=params,
            json=json_body,
            headers=headers,
            timeout=self.timeout_seconds,
        )
        return self._parse_json_response(response, context=f"call SP-API {method} {path}")

    def _validate_lwa_settings(self) -> None:
        missing = [
            name
            for name, value in {
                "AMAZON_LWA_CLIENT_ID": self.settings.amazon_lwa_client_id,
                "AMAZON_LWA_CLIENT_SECRET": self.settings.amazon_lwa_client_secret,
                "AMAZON_SP_API_REFRESH_TOKEN": self.settings.amazon_sp_api_refresh_token,
            }.items()
            if not value
        ]
        if missing:
            raise ConfigurationError(
                "Missing required Amazon SP-API environment variables: " + ", ".join(missing)
            )

    @staticmethod
    def _parse_json_response(response: requests.Response, *, context: str) -> dict[str, Any]:
        if not 200 <= response.status_code < 300:
            message = response.text[:1000] if response.text else ""
            raise ExternalServiceError(
                f"Failed to {context}: HTTP {response.status_code}. Response: {message}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ExternalServiceError(f"Failed to {context}: response was not valid JSON") from exc

        if not isinstance(payload, dict):
            raise ExternalServiceError(f"Failed to {context}: JSON response was not an object")
        return payload


def _format_sp_api_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
