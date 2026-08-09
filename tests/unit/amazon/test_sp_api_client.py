from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime
from typing import Any

import pytest

from seller_data_pipeline.common.exceptions import ConfigurationError, ExternalServiceError
from seller_data_pipeline.config.settings import Settings
from seller_data_pipeline.integrations.amazon.sp_api_client import AmazonSpApiClient


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload: dict[str, Any] | None = None,
        content: bytes | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = json.dumps(self._payload)
        self.content = content if content is not None else self.text.encode("utf-8")

    def json(self) -> dict[str, Any]:
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
        if self.next_request_response is not None:
            return self.next_request_response
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

    def get(self, url: str, timeout: int) -> FakeResponse:
        self.get_calls.append({"url": url, "timeout": timeout})
        if self.next_get_response is not None:
            return self.next_get_response
        return FakeResponse(200, content=b"sku\tprice\nABC\t9.99\n")


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


def test_create_report_posts_reports_api_payload() -> None:
    session = FakeSession()
    session.next_request_response = FakeResponse(202, {"reportId": "report-123"})
    client = AmazonSpApiClient(settings=_settings(), session=session)  # type: ignore[arg-type]

    result = client.create_report(
        report_type="GET_MERCHANT_LISTINGS_ALL_DATA",
        marketplace_ids=["ATVPDKIKX0DER"],
        data_start_time=datetime(2026, 5, 1, tzinfo=UTC),
        data_end_time=datetime(2026, 5, 2, tzinfo=UTC),
    )

    assert result.report_id == "report-123"
    request_call = session.request_calls[0]
    assert request_call["method"] == "POST"
    assert request_call["url"].endswith("/reports/2021-06-30/reports")
    assert request_call["json"] == {
        "reportType": "GET_MERCHANT_LISTINGS_ALL_DATA",
        "marketplaceIds": ["ATVPDKIKX0DER"],
        "dataStartTime": "2026-05-01T00:00:00Z",
        "dataEndTime": "2026-05-02T00:00:00Z",
    }


def test_get_report_and_document_use_expected_paths() -> None:
    session = FakeSession()
    session.next_request_response = FakeResponse(
        200,
        {"reportId": "report-123", "processingStatus": "DONE"},
    )
    client = AmazonSpApiClient(settings=_settings(), session=session)  # type: ignore[arg-type]

    report = client.get_report(report_id="report-123")

    assert report["processingStatus"] == "DONE"
    assert session.request_calls[0]["method"] == "GET"
    assert session.request_calls[0]["url"].endswith("/reports/2021-06-30/reports/report-123")

    session.next_request_response = FakeResponse(
        200,
        {"reportDocumentId": "doc-123", "url": "https://example.test/doc"},
    )
    document = client.get_report_document(report_document_id="doc-123")

    assert document["reportDocumentId"] == "doc-123"
    assert session.request_calls[1]["method"] == "GET"
    assert session.request_calls[1]["url"].endswith("/reports/2021-06-30/documents/doc-123")


def test_download_report_document_decompresses_gzip() -> None:
    session = FakeSession()
    compressed = gzip.compress(b"sku\tprice\nABC\t9.99\n")
    session.next_get_response = FakeResponse(200, content=compressed)
    client = AmazonSpApiClient(settings=_settings(), session=session)  # type: ignore[arg-type]

    result = client.download_report_document(
        document_url="https://example.test/doc",
        compression_algorithm="GZIP",
    )

    assert result.content == b"sku\tprice\nABC\t9.99\n"
    assert result.decompressed is True
    assert result.raw_size_bytes == len(compressed)


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

    client = AmazonSpApiClient(
        settings=_settings(),
        session=ErrorSession(),  # type: ignore[arg-type]
    )

    with pytest.raises(ExternalServiceError, match="HTTP 401"):
        client.get_lwa_access_token()


def test_get_reports_uses_expected_filters() -> None:
    session = FakeSession()
    session.next_request_response = FakeResponse(
        200,
        {
            "reports": [
                {
                    "reportId": "report-123",
                    "reportType": "GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2",
                    "processingStatus": "DONE",
                }
            ]
        },
    )
    client = AmazonSpApiClient(settings=_settings(), session=session)  # type: ignore[arg-type]

    payload = client.get_reports(
        report_types=["GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2"],
        processing_statuses=["DONE"],
        marketplace_ids=["ATVPDKIKX0DER"],
        page_size=20,
        created_since=datetime(2026, 5, 1, tzinfo=UTC),
        created_until=datetime(2026, 5, 14, tzinfo=UTC),
    )

    assert payload["reports"][0]["reportId"] == "report-123"
    request_call = session.request_calls[0]
    assert request_call["method"] == "GET"
    assert request_call["url"].endswith("/reports/2021-06-30/reports")
    assert request_call["params"] == {
        "reportTypes": ["GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2"],
        "processingStatuses": ["DONE"],
        "marketplaceIds": ["ATVPDKIKX0DER"],
        "pageSize": 20,
        "createdSince": "2026-05-01T00:00:00Z",
        "createdUntil": "2026-05-14T00:00:00Z",
    }


def test_get_reports_with_next_token_only() -> None:
    session = FakeSession()
    session.next_request_response = FakeResponse(200, {"reports": []})
    client = AmazonSpApiClient(settings=_settings(), session=session)  # type: ignore[arg-type]

    client.get_reports(report_types=["ignored"], next_token="next-1")

    assert session.request_calls[0]["params"] == {"nextToken": "next-1"}


def test_list_finance_transactions_uses_v2024_filters_and_preserves_them_with_next_token() -> None:
    session = FakeSession()
    session.next_request_response = FakeResponse(
        200,
        {"payload": {"transactions": [], "nextToken": "next-1"}},
    )
    client = AmazonSpApiClient(settings=_settings(), session=session)  # type: ignore[arg-type]

    payload = client.list_finance_transactions(
        posted_after=datetime(2026, 7, 1, tzinfo=UTC),
        posted_before=datetime(2026, 8, 1, tzinfo=UTC),
        marketplace_id="ATVPDKIKX0DER",
        transaction_status="RELEASED",
        next_token="next-1",
    )

    assert payload["payload"]["nextToken"] == "next-1"
    request_call = session.request_calls[0]
    assert request_call["method"] == "GET"
    assert request_call["url"].endswith("/finances/2024-06-19/transactions")
    assert request_call["params"] == {
        "postedAfter": "2026-07-01T00:00:00Z",
        "postedBefore": "2026-08-01T00:00:00Z",
        "marketplaceId": "ATVPDKIKX0DER",
        "transactionStatus": "RELEASED",
        "nextToken": "next-1",
    }


def test_list_finance_transactions_validates_required_filter_pairs() -> None:
    client = AmazonSpApiClient(settings=_settings(), session=FakeSession())  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="posted_after or related_identifier_name"):
        client.list_finance_transactions()

    with pytest.raises(ValueError, match="provided together"):
        client.list_finance_transactions(
            related_identifier_name="ORDER_ID",
            related_identifier_value=None,
        )

    with pytest.raises(ValueError, match="transaction_status"):
        client.list_finance_transactions(
            posted_after=datetime(2026, 7, 1, tzinfo=UTC),
            transaction_status="UNKNOWN",
        )
