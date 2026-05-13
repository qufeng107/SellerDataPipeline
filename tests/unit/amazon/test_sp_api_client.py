from __future__ import annotations

import json
from typing import Any

import pytest
from seller_data_pipeline.common.exceptions import ConfigurationError, ExternalServiceError
from seller_data_pipeline.config.settings import Settings
from seller_data_pipeline.integrations.amazon.sp_api_client import AmazonSpApiClient


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = json.dumps(self._payload)

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeSession:
    def __init__(self) -> None:
        self.post_calls: list[dict[str, Any]] = []
        self.request_calls: list[dict[str, Any]] = []

    def post(self, url: str, data: dict[str, Any], timeout: int) -> FakeResponse:
        self.post_calls.append({"url": url, "data": data, "timeout": timeout})
        return FakeResponse(
            200,
            {
                "access_token": "test-access-token",
                "token_type": "bearer",
                "expires_in": 3600,
            },
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
        return FakeResponse(
            200,
            {
                "payload": [
                    {
                        "marketplace": {
                            "id": "ATVPDKIKX0DER",
                            "name": "Amazon.com",
                            "countryCode": "US",
                            "defaultCurrencyCode": "USD",
                        }
                    }
                ]
            },
        )


def _settings() -> Settings:
    return Settings(
        amazon_lwa_client_id="client-id",
        amazon_lwa_client_secret="client-secret",
        amazon_sp_api_refresh_token="refresh-token",
        amazon_sp_api_endpoint="https://sellingpartnerapi-na.amazon.com",
        amazon_lwa_token_url="https://api.amazon.com/auth/o2/token",
        amazon_sp_api_user_agent="SellerDataPipeline/0.1.0 (Language=Python/3.11)",
    )


def test_get_marketplace_participations_uses_lwa_token_header() -> None:
    session = FakeSession()
    client = AmazonSpApiClient(settings=_settings(), session=session)  # type: ignore[arg-type]

    payload = client.get_marketplace_participations()

    assert payload["payload"][0]["marketplace"]["id"] == "ATVPDKIKX0DER"
    assert session.post_calls[0]["data"]["grant_type"] == "refresh_token"
    assert session.post_calls[0]["data"]["refresh_token"] == "refresh-token"
    assert session.request_calls[0]["method"] == "GET"
    assert session.request_calls[0]["url"].endswith("/sellers/v1/marketplaceParticipations")
    assert session.request_calls[0]["headers"]["x-amz-access-token"] == "test-access-token"
    assert "x-amz-date" in session.request_calls[0]["headers"]


def test_missing_lwa_settings_raises_configuration_error() -> None:
    settings = Settings(
        amazon_lwa_client_id=None,
        amazon_lwa_client_secret="client-secret",
        amazon_sp_api_refresh_token="refresh-token",
    )
    client = AmazonSpApiClient(settings=settings)

    with pytest.raises(ConfigurationError, match="AMAZON_LWA_CLIENT_ID"):
        client.get_lwa_access_token()


def test_lwa_http_error_raises_external_service_error() -> None:
    class ErrorSession(FakeSession):
        def post(self, url: str, data: dict[str, Any], timeout: int) -> FakeResponse:
            return FakeResponse(401, {"error": "invalid_client"})

    client = AmazonSpApiClient(settings=_settings(), session=ErrorSession())  # type: ignore[arg-type]

    with pytest.raises(ExternalServiceError, match="HTTP 401"):
        client.get_lwa_access_token()
