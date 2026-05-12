from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Any

import requests

from seller_data_pipeline.common.exceptions import ConfigurationError, ExternalServiceError
from seller_data_pipeline.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LwaAccessToken:
    access_token: str
    token_type: str
    expires_in: int


@dataclass(frozen=True)
class ReportRequestResult:
    report_id: str


class AmazonSpApiClient:
    """Small HTTP client for Amazon SP-API.

    This class only owns API/auth details. Business orchestration should stay in services.
    The current implementation uses the simplified LWA-only SP-API request flow and does not
    implement restricted-data-token operations.
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

        # Refresh a little early so long-running jobs do not hit the exact expiry boundary.
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
    ) -> ReportRequestResult:
        logger.info(
            "create_report placeholder: report_type=%s marketplace_ids=%s start=%s end=%s",
            report_type,
            marketplace_ids,
            data_start_time,
            data_end_time,
        )
        raise NotImplementedError("Amazon SP-API create_report is not implemented yet")

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
