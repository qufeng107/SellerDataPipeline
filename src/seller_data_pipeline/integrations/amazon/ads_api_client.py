from __future__ import annotations

import gzip
import json
import logging
from dataclasses import dataclass
from datetime import date
from time import monotonic
from typing import Any

import requests

from seller_data_pipeline.common.exceptions import ConfigurationError, ExternalServiceError
from seller_data_pipeline.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

ADS_CREATE_REPORT_ACCEPT = "application/vnd.createasyncreportresponse.v3+json"
ADS_CREATE_REPORT_CONTENT_TYPE = "application/vnd.createasyncreportrequest.v3+json"
ADS_GET_REPORT_ACCEPT = "application/vnd.getasyncreportresponse.v3+json"
DEFAULT_ADS_REPORT_FORMAT = "GZIP_JSON"


@dataclass(frozen=True)
class AdsLwaAccessToken:
    access_token: str
    token_type: str
    expires_in: int


@dataclass(frozen=True)
class AdsReportRequestResult:
    report_id: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class DownloadedAdsReport:
    content: bytes
    raw_size_bytes: int
    decompressed: bool


class AmazonAdsApiClient:
    """Small HTTP client for Amazon Ads API local sampling.

    The first implementation intentionally focuses on read-only discovery and Reporting v3.
    It does not create or mutate campaigns.
    """

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
        self._cached_token: AdsLwaAccessToken | None = None
        self._cached_token_expires_at = 0.0

    def get_lwa_access_token(self) -> AdsLwaAccessToken:
        """Exchange the Ads refresh token for a short-lived LWA access token."""

        if self._cached_token and monotonic() < self._cached_token_expires_at:
            return self._cached_token

        self._validate_ads_lwa_settings()
        response = self.session.post(
            self.settings.amazon_lwa_token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.settings.amazon_ads_refresh_token,
                "client_id": self.settings.amazon_ads_client_id,
                "client_secret": self.settings.amazon_ads_client_secret,
            },
            timeout=self.timeout_seconds,
        )
        payload = self._parse_json_response(response, context="request Amazon Ads LWA token")

        try:
            token = AdsLwaAccessToken(
                access_token=str(payload["access_token"]),
                token_type=str(payload.get("token_type", "bearer")),
                expires_in=int(payload.get("expires_in", 3600)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ExternalServiceError("Amazon Ads LWA response did not contain a token") from exc

        self._cached_token = token
        self._cached_token_expires_at = monotonic() + max(token.expires_in - 60, 60)
        return token

    def list_profiles(self) -> list[dict[str, Any]]:
        """Return Amazon Ads profiles available to the authorized Ads user."""

        payload = self._request_json(
            "GET",
            "/v2/profiles",
            scope_profile_id=None,
            accept="application/json",
        )
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload.get("profiles"), list):
            return [item for item in payload["profiles"] if isinstance(item, dict)]
        if isinstance(payload.get("payload"), list):
            return [item for item in payload["payload"] if isinstance(item, dict)]
        raise ExternalServiceError("Amazon Ads profiles response was not a list")

    def create_report(
        self,
        *,
        profile_id: str,
        name: str,
        start_date: date,
        end_date: date,
        ad_product: str,
        report_type_id: str,
        group_by: list[str],
        columns: list[str],
        time_unit: str = "DAILY",
        filters: list[dict[str, Any]] | None = None,
    ) -> AdsReportRequestResult:
        """Create an Amazon Ads Reporting v3 asynchronous report request."""

        if not profile_id:
            raise ValueError("profile_id is required")
        if not report_type_id:
            raise ValueError("report_type_id is required")
        if not group_by:
            raise ValueError("group_by must contain at least one value")
        if not columns:
            raise ValueError("columns must contain at least one value")
        if end_date < start_date:
            raise ValueError("end_date must be on or after start_date")

        configuration: dict[str, Any] = {
            "adProduct": ad_product,
            "columns": columns,
            "format": DEFAULT_ADS_REPORT_FORMAT,
            "groupBy": group_by,
            "reportTypeId": report_type_id,
            "timeUnit": time_unit,
        }
        if filters:
            configuration["filters"] = filters

        body = {
            "configuration": configuration,
            "endDate": end_date.isoformat(),
            "name": name,
            "startDate": start_date.isoformat(),
        }
        payload = self._request_json(
            "POST",
            "/reporting/reports",
            scope_profile_id=profile_id,
            json_body=body,
            accept=ADS_CREATE_REPORT_ACCEPT,
            content_type=ADS_CREATE_REPORT_CONTENT_TYPE,
        )
        report_id = str(payload.get("reportId") or "")
        if not report_id:
            raise ExternalServiceError("Amazon Ads create report response did not contain reportId")
        return AdsReportRequestResult(report_id=report_id, payload=payload)

    def get_report(self, *, profile_id: str, report_id: str) -> dict[str, Any]:
        """Return current status for an Amazon Ads Reporting v3 report."""

        if not profile_id:
            raise ValueError("profile_id is required")
        if not report_id:
            raise ValueError("report_id is required")
        return self._request_json(
            "GET",
            f"/reporting/reports/{report_id}",
            scope_profile_id=profile_id,
            accept=ADS_GET_REPORT_ACCEPT,
        )

    def download_report(self, *, document_url: str) -> DownloadedAdsReport:
        """Download the generated report document URL returned by Reporting v3."""

        if not document_url:
            raise ValueError("document_url is required")
        response = self.session.get(document_url, timeout=self.timeout_seconds)
        if not 200 <= response.status_code < 300:
            message = response.text[:1000] if response.text else ""
            raise ExternalServiceError(
                "Failed to download Amazon Ads report: "
                f"HTTP {response.status_code}. Response: {message}"
            )
        raw_content = response.content
        try:
            content = gzip.decompress(raw_content)
            return DownloadedAdsReport(
                content=content,
                raw_size_bytes=len(raw_content),
                decompressed=True,
            )
        except OSError:
            logger.warning("Amazon Ads report was expected to be GZIP_JSON but was not gzipped")
            return DownloadedAdsReport(
                content=raw_content,
                raw_size_bytes=len(raw_content),
                decompressed=False,
            )

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        scope_profile_id: str | None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        accept: str = "application/json",
        content_type: str = "application/json",
    ) -> dict[str, Any] | list[Any]:
        token = self.get_lwa_access_token()
        url = f"{self.settings.amazon_ads_api_endpoint.rstrip('/')}/{path.lstrip('/')}"
        headers = {
            "accept": accept,
            "authorization": f"Bearer {token.access_token}",
            "content-type": content_type,
            "user-agent": self.settings.amazon_ads_user_agent,
            "Amazon-Advertising-API-ClientId": str(self.settings.amazon_ads_client_id),
        }
        if scope_profile_id:
            headers["Amazon-Advertising-API-Scope"] = str(scope_profile_id)

        response = self.session.request(
            method=method,
            url=url,
            params=params,
            json=json_body,
            headers=headers,
            timeout=self.timeout_seconds,
        )
        return self._parse_json_response(response, context=f"call Ads API {method} {path}")

    def _validate_ads_lwa_settings(self) -> None:
        missing = [
            name
            for name, value in {
                "AMAZON_ADS_CLIENT_ID": self.settings.amazon_ads_client_id,
                "AMAZON_ADS_CLIENT_SECRET": self.settings.amazon_ads_client_secret,
                "AMAZON_ADS_REFRESH_TOKEN": self.settings.amazon_ads_refresh_token,
            }.items()
            if not value
        ]
        if missing:
            raise ConfigurationError(
                "Missing required Amazon Ads API environment variables: " + ", ".join(missing)
            )

    @staticmethod
    def _parse_json_response(
        response: requests.Response,
        *,
        context: str,
    ) -> dict[str, Any] | list[Any]:
        if not 200 <= response.status_code < 300:
            message = response.text[:1000] if response.text else ""
            raise ExternalServiceError(
                f"Failed to {context}: HTTP {response.status_code}. Response: {message}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ExternalServiceError(f"Failed to {context}: response was not valid JSON") from exc
        if not isinstance(payload, dict | list):
            raise ExternalServiceError(f"Failed to {context}: JSON response was not an object/list")
        return payload


def compact_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
