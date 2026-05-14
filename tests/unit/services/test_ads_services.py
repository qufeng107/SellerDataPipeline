from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from seller_data_pipeline.config.settings import Settings
from seller_data_pipeline.sampling.ads_manifest_store import AdsManifestStore
from seller_data_pipeline.sampling.ads_raw_report_files import AdsRawReportFileStore
from seller_data_pipeline.services.collect_ads_reports_service import CollectAdsReportsService
from seller_data_pipeline.services.discover_ads_profiles_service import DiscoverAdsProfilesService
from seller_data_pipeline.services.submit_ads_report_requests_service import (
    SubmitAdsReportRequestsService,
)


@dataclass(frozen=True)
class FakeAdsReportResult:
    report_id: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class FakeDownloadedAdsReport:
    content: bytes
    raw_size_bytes: int
    decompressed: bool


class FakeAdsApiClient:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, Any]] = []
        self.get_report_calls: list[dict[str, Any]] = []
        self.download_calls: list[str] = []

    def list_profiles(self) -> list[dict[str, Any]]:
        return [{"profileId": 123, "countryCode": "US"}]

    def create_report(self, **kwargs: Any) -> FakeAdsReportResult:
        self.create_calls.append(kwargs)
        return FakeAdsReportResult(report_id="ads-report-123", payload={"status": "PENDING"})

    def get_report(self, *, profile_id: str, report_id: str) -> dict[str, Any]:
        self.get_report_calls.append({"profile_id": profile_id, "report_id": report_id})
        return {"reportId": report_id, "status": "COMPLETED", "url": "https://example.test/report"}

    def download_report(self, *, document_url: str) -> FakeDownloadedAdsReport:
        self.download_calls.append(document_url)
        return FakeDownloadedAdsReport(
            content=b'[{"campaignId":"1","clicks":2}]',
            raw_size_bytes=50,
            decompressed=True,
        )


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        local_sampling_root=str(tmp_path / "sampling"),
        raw_reports_root=str(tmp_path / "raw"),
        amazon_ads_profile_id="123",
        amazon_ads_client_id="client",
        amazon_ads_client_secret="secret",
        amazon_ads_refresh_token="refresh",
    )


def test_discover_ads_profiles_saves_manifest(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    store = AdsManifestStore(root_dir=settings.local_sampling_root)
    service = DiscoverAdsProfilesService(
        settings=settings,
        ads_api_client=FakeAdsApiClient(),  # type: ignore[arg-type]
        manifest_store=store,
    )

    path = service.run()

    assert path.exists()
    assert store.read_profiles()[0]["profileId"] == 123


def test_submit_ads_report_request_saves_manifest(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    fake_client = FakeAdsApiClient()
    store = AdsManifestStore(root_dir=settings.local_sampling_root)
    service = SubmitAdsReportRequestsService(
        settings=settings,
        ads_api_client=fake_client,  # type: ignore[arg-type]
        manifest_store=store,
    )

    path = service.run(
        profile_id=None,
        report_type_id="spCampaigns",
        ad_product="SPONSORED_PRODUCTS",
        group_by=["campaign"],
        columns=["date", "campaignId", "clicks"],
        days=7,
    )

    assert path.exists()
    manifest = store.read_report_request("ads-report-123")
    assert manifest["source_system"] == "amazon_ads"
    assert manifest["profile_id"] == "123"
    assert manifest["report_type_id"] == "spCampaigns"
    assert manifest["processing_status"] == "PENDING"
    assert fake_client.create_calls[0]["columns"] == ["date", "campaignId", "clicks"]


def test_collect_ads_reports_downloads_completed_report(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    fake_client = FakeAdsApiClient()
    store = AdsManifestStore(root_dir=settings.local_sampling_root)
    raw_store = AdsRawReportFileStore(root_dir=settings.raw_reports_root)
    store.save_report_request(
        {
            "source_system": "amazon_ads",
            "ads_report_id": "ads-report-123",
            "profile_id": "123",
            "report_type_id": "spCampaigns",
            "ad_product": "SPONSORED_PRODUCTS",
            "group_by": ["campaign"],
            "columns": ["date", "campaignId", "clicks"],
            "time_unit": "DAILY",
            "data_start_date": "2026-05-01",
            "data_end_date": "2026-05-07",
            "processing_status": "PENDING",
            "download_status": "NOT_STARTED",
        }
    )
    service = CollectAdsReportsService(
        settings=settings,
        ads_api_client=fake_client,  # type: ignore[arg-type]
        manifest_store=store,
        raw_file_store=raw_store,
    )

    results = service.run(limit=10)

    assert len(results) == 1
    manifest = store.read_report_request("ads-report-123")
    assert manifest["processing_status"] == "COMPLETED"
    assert manifest["download_status"] == "DOWNLOADED"
    assert Path(manifest["raw_file_path"]).exists()
    assert fake_client.download_calls == ["https://example.test/report"]
