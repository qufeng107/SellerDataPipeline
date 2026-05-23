from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from seller_data_pipeline.config.settings import Settings
from seller_data_pipeline.sampling.ads_manifest_store import AdsManifestStore
from seller_data_pipeline.sampling.local_manifest_store import LocalManifestStore
from seller_data_pipeline.services.historical_backfill_service import (
    BackfillAdsReportsService,
    BackfillReportRequestsService,
    build_backfill_windows,
)


@dataclass(frozen=True)
class FakeReportRequestResult:
    report_id: str
    payload: dict[str, Any]


class FakeSpApiClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create_report(self, **kwargs: Any) -> FakeReportRequestResult:
        self.calls.append(kwargs)
        report_id = f"sp-report-{len(self.calls)}"
        return FakeReportRequestResult(report_id=report_id, payload={"reportId": report_id})


@dataclass(frozen=True)
class FakeAdsReportResult:
    report_id: str
    payload: dict[str, Any]


class FakeAdsApiClient:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, Any]] = []

    def create_report(self, **kwargs: Any) -> FakeAdsReportResult:
        self.create_calls.append(kwargs)
        report_id = f"ads-report-{len(self.create_calls)}"
        return FakeAdsReportResult(report_id=report_id, payload={"status": "PENDING"})


def test_build_backfill_windows_uses_inclusive_chunks() -> None:
    windows = build_backfill_windows(
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
        chunk_days=14,
    )

    assert [(window.start, window.end) for window in windows] == [
        (date(2026, 3, 1), date(2026, 3, 14)),
        (date(2026, 3, 15), date(2026, 3, 28)),
        (date(2026, 3, 29), date(2026, 3, 31)),
    ]


def test_sp_api_backfill_dry_run_plans_without_submitting(tmp_path: Path) -> None:
    settings = _sp_settings(tmp_path)
    fake_client = FakeSpApiClient()
    store = LocalManifestStore(root_dir=settings.local_sampling_root)
    submit_service = _sp_submit_service(settings, fake_client, store)
    service = BackfillReportRequestsService(
        settings=settings,
        manifest_store=store,
        submit_service=submit_service,
    )

    result = service.run(
        report_type="GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL",
        marketplace_ids=None,
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
        chunk_days=30,
        dry_run=True,
    )

    assert result.dry_run is True
    assert result.created_count == 0
    assert result.total_count == 2
    assert fake_client.calls == []
    assert result.window_results[0].status == "dry_run_planned"


def test_sp_api_backfill_submits_explicit_inclusive_windows(tmp_path: Path) -> None:
    settings = _sp_settings(tmp_path)
    fake_client = FakeSpApiClient()
    store = LocalManifestStore(root_dir=settings.local_sampling_root)
    submit_service = _sp_submit_service(settings, fake_client, store)
    service = BackfillReportRequestsService(
        settings=settings,
        manifest_store=store,
        submit_service=submit_service,
    )

    result = service.run(
        report_type="GET_SALES_AND_TRAFFIC_REPORT",
        marketplace_ids=None,
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
        chunk_days=31,
        dry_run=False,
        pause_seconds=0,
    )

    assert result.created_count == 1
    assert fake_client.calls[0]["data_start_time"].isoformat().startswith("2026-03-01")
    assert fake_client.calls[0]["data_end_time"].isoformat().startswith("2026-04-01")
    manifest = store.read_report_request("sp-report-1")
    assert manifest["data_start_time"] == "2026-03-01T00:00:00Z"
    assert manifest["data_end_time"] == "2026-04-01T00:00:00Z"


def test_sp_api_backfill_skips_matching_existing_manifest(tmp_path: Path) -> None:
    settings = _sp_settings(tmp_path)
    fake_client = FakeSpApiClient()
    store = LocalManifestStore(root_dir=settings.local_sampling_root)
    store.save_report_request(
        {
            "report_id": "existing-report",
            "report_type": "GET_SALES_AND_TRAFFIC_REPORT",
            "marketplace_ids": ["ATVPDKIKX0DER"],
            "data_start_time": "2026-03-01T00:00:00Z",
            "data_end_time": "2026-04-01T00:00:00Z",
            "report_options": {},
            "processing_status": "DONE",
            "download_status": "DOWNLOADED",
        }
    )
    submit_service = _sp_submit_service(settings, fake_client, store)
    service = BackfillReportRequestsService(
        settings=settings,
        manifest_store=store,
        submit_service=submit_service,
    )

    result = service.run(
        report_type="GET_SALES_AND_TRAFFIC_REPORT",
        marketplace_ids=None,
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
        chunk_days=31,
        dry_run=False,
        pause_seconds=0,
    )

    assert result.skipped_count == 1
    assert fake_client.calls == []


def test_ads_backfill_submits_filtered_plan_items(tmp_path: Path) -> None:
    settings = _ads_settings(tmp_path)
    fake_client = FakeAdsApiClient()
    store = AdsManifestStore(root_dir=settings.local_sampling_root)
    submit_service = _ads_submit_service(settings, fake_client, store)
    service = BackfillAdsReportsService(
        settings=settings,
        manifest_store=store,
        submit_service=submit_service,
    )

    result = service.run(
        profile_id=None,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 17),
        chunk_days=14,
        only_report_type_ids=["spCampaigns"],
        dry_run=False,
        pause_seconds=0,
    )

    assert result.created_count == 2
    assert [call["report_type_id"] for call in fake_client.create_calls] == [
        "spCampaigns",
        "spCampaigns",
    ]
    assert fake_client.create_calls[0]["start_date"] == date(2026, 5, 1)
    assert fake_client.create_calls[0]["end_date"] == date(2026, 5, 14)
    assert fake_client.create_calls[1]["start_date"] == date(2026, 5, 15)
    assert fake_client.create_calls[1]["end_date"] == date(2026, 5, 17)


def _sp_settings(tmp_path: Path) -> Settings:
    return Settings(
        amazon_marketplace_id="ATVPDKIKX0DER",
        local_sampling_root=str(tmp_path / "sampling"),
    )


def _ads_settings(tmp_path: Path) -> Settings:
    return Settings(
        amazon_ads_profile_id="123",
        local_sampling_root=str(tmp_path / "sampling"),
        amazon_ads_client_id="client",
        amazon_ads_client_secret="secret",
        amazon_ads_refresh_token="refresh",
    )


def _sp_submit_service(settings: Settings, fake_client: FakeSpApiClient, store: LocalManifestStore):
    from seller_data_pipeline.services.submit_report_requests_service import (
        SubmitReportRequestsService,
    )

    return SubmitReportRequestsService(
        settings=settings,
        sp_api_client=fake_client,  # type: ignore[arg-type]
        manifest_store=store,
    )


def _ads_submit_service(settings: Settings, fake_client: FakeAdsApiClient, store: AdsManifestStore):
    from seller_data_pipeline.services.submit_ads_report_requests_service import (
        SubmitAdsReportRequestsService,
    )

    return SubmitAdsReportRequestsService(
        settings=settings,
        ads_api_client=fake_client,  # type: ignore[arg-type]
        manifest_store=store,
    )
