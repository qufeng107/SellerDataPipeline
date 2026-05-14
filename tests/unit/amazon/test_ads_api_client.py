from __future__ import annotations

import gzip
import json
from datetime import date
from typing import Any

import pytest

from seller_data_pipeline.common.exceptions import ConfigurationError, ExternalServiceError
from seller_data_pipeline.config.settings import Settings
from seller_data_pipeline.integrations.amazon.ads_api_client import AmazonAdsApiClient


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload: dict[str, Any] | list[Any] | None = None,
        content: bytes | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = json.dumps(self._payload)
        self.content = content if content is not None else self.text.encode("utf-8")

    def json(self) -> dict[str, Any] | list[Any]:
        return self._payload


class FakeSession:
    def __init__(self) -> None:
        self.post_calls: list[dict[str, Any]] = []
        self.request_calls: list[dict[str, Any]] = []
        self.get_calls: list[dict[str, Any]] = []
        self.next_request_response: FakeResponse | None = None
        self.next_get_response: FakeResponse | None = None

    def post(self, url: str, data: dict[str, Any], timeout: int) -> FakeResponse:
        self.post_calls.append({"url": url, "data": data, "timeout": timeout})
        return FakeResponse(
            200,
            {"access_token": "ads-token", "token_type": "bearer", "expires_in": 3600},
        )

    def request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None,
        json: dict[str, Any] | None,
        headers: dict[str, Any],
        timeout: int,
    ) -> FakeResponse:
        self.request_calls.append(
            {
                "method": method,
                "url": url,
                "params": params,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        if self.next_request_response is not None:
            return self.next_request_response
        return FakeResponse(200, [])

    def get(self, url: str, timeout: int) -> FakeResponse:
        self.get_calls.append({"url": url, "timeout": timeout})
        if self.next_get_response is not None:
            return self.next_get_response
        return FakeResponse(200, content=b"[]")


def _settings() -> Settings:
    return Settings(
        amazon_ads_client_id="ads-client-id",
        amazon_ads_client_secret="ads-client-secret",
        amazon_ads_refresh_token="ads-refresh-token",
        amazon_ads_api_endpoint="https://advertising-api.amazon.com",
        amazon_lwa_token_url="https://api.amazon.com/auth/o2/token",
    )


def test_list_profiles_uses_ads_headers_without_scope() -> None:
    session = FakeSession()
    session.next_request_response = FakeResponse(200, [{"profileId": 123, "countryCode": "US"}])
    client = AmazonAdsApiClient(settings=_settings(), session=session)  # type: ignore[arg-type]

    profiles = client.list_profiles()

    assert profiles[0]["profileId"] == 123
    assert session.post_calls[0]["data"]["refresh_token"] == "ads-refresh-token"
    call = session.request_calls[0]
    assert call["method"] == "GET"
    assert call["url"].endswith("/v2/profiles")
    assert call["headers"]["authorization"] == "Bearer ads-token"
    assert call["headers"]["Amazon-Advertising-API-ClientId"] == "ads-client-id"
    assert "Amazon-Advertising-API-Scope" not in call["headers"]


def test_create_report_posts_reporting_v3_body_and_headers() -> None:
    session = FakeSession()
    session.next_request_response = FakeResponse(
        200,
        {"reportId": "ads-report-1", "status": "PENDING"},
    )
    client = AmazonAdsApiClient(settings=_settings(), session=session)  # type: ignore[arg-type]

    result = client.create_report(
        profile_id="1234567890",
        name="test report",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 7),
        ad_product="SPONSORED_PRODUCTS",
        report_type_id="spCampaigns",
        group_by=["campaign"],
        columns=["date", "campaignId", "clicks"],
    )

    assert result.report_id == "ads-report-1"
    call = session.request_calls[0]
    assert call["method"] == "POST"
    assert call["url"].endswith("/reporting/reports")
    assert call["headers"]["Amazon-Advertising-API-Scope"] == "1234567890"
    assert call["headers"]["content-type"] == "application/vnd.createasyncreportrequest.v3+json"
    assert call["json"] == {
        "configuration": {
            "adProduct": "SPONSORED_PRODUCTS",
            "columns": ["date", "campaignId", "clicks"],
            "format": "GZIP_JSON",
            "groupBy": ["campaign"],
            "reportTypeId": "spCampaigns",
            "timeUnit": "DAILY",
        },
        "endDate": "2026-05-07",
        "name": "test report",
        "startDate": "2026-05-01",
    }


def test_get_report_uses_reporting_v3_status_path() -> None:
    session = FakeSession()
    session.next_request_response = FakeResponse(
        200,
        {"reportId": "ads-report-1", "status": "COMPLETED"},
    )
    client = AmazonAdsApiClient(settings=_settings(), session=session)  # type: ignore[arg-type]

    payload = client.get_report(profile_id="123", report_id="ads-report-1")

    assert payload["status"] == "COMPLETED"
    call = session.request_calls[0]
    assert call["method"] == "GET"
    assert call["url"].endswith("/reporting/reports/ads-report-1")
    assert call["headers"]["Amazon-Advertising-API-Scope"] == "123"


def test_download_ads_report_decompresses_gzip_json() -> None:
    session = FakeSession()
    compressed = gzip.compress(b'[{"campaignId":"1","clicks":2}]')
    session.next_get_response = FakeResponse(200, content=compressed)
    client = AmazonAdsApiClient(settings=_settings(), session=session)  # type: ignore[arg-type]

    result = client.download_report(document_url="https://example.test/report")

    assert result.content == b'[{"campaignId":"1","clicks":2}]'
    assert result.decompressed is True
    assert result.raw_size_bytes == len(compressed)


def test_missing_ads_settings_raises_configuration_error() -> None:
    settings = Settings(amazon_ads_client_id=None, amazon_ads_client_secret="secret")
    client = AmazonAdsApiClient(settings=settings)

    with pytest.raises(ConfigurationError, match="AMAZON_ADS_CLIENT_ID"):
        client.get_lwa_access_token()


def test_ads_http_error_raises_external_service_error() -> None:
    class ErrorSession(FakeSession):
        def post(self, url: str, data: dict[str, Any], timeout: int) -> FakeResponse:
            return FakeResponse(401, {"error": "invalid_client"})

    client = AmazonAdsApiClient(
        settings=_settings(),
        session=ErrorSession(),  # type: ignore[arg-type]
    )

    with pytest.raises(ExternalServiceError, match="HTTP 401"):
        client.get_lwa_access_token()
