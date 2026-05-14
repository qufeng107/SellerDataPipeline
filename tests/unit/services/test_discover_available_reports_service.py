from __future__ import annotations

from datetime import date, timedelta

from seller_data_pipeline.config.settings import Settings
from seller_data_pipeline.services.discover_available_reports_service import (
    DiscoverAvailableReportsService,
)
from seller_data_pipeline.sampling.local_manifest_store import LocalManifestStore


class FakeReportsClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def get_reports(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(kwargs)
        return {
            "reports": [
                {
                    "reportId": "settlement-1",
                    "reportType": "GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2",
                    "processingStatus": "DONE",
                    "reportDocumentId": "doc-1",
                    "marketplaceIds": ["ATVPDKIKX0DER"],
                    "createdTime": "2026-05-14T00:00:00Z",
                    "processingEndTime": "2026-05-14T00:01:00Z",
                }
            ]
        }


def _settings(tmp_path) -> Settings:  # type: ignore[no-untyped-def]
    return Settings(
        amazon_marketplace_id="ATVPDKIKX0DER",
        local_sampling_root=str(tmp_path / "runtime" / "sampling"),
    )


def test_discover_available_reports_saves_report_request_manifest(tmp_path) -> None:  # type: ignore[no-untyped-def]
    client = FakeReportsClient()
    store = LocalManifestStore(root_dir=tmp_path / "runtime" / "sampling")
    service = DiscoverAvailableReportsService(
        settings=_settings(tmp_path),
        sp_api_client=client,  # type: ignore[arg-type]
        manifest_store=store,
    )

    paths = service.run(days=7, today=date(2026, 5, 14), page_size=20, max_pages=1)

    assert len(paths) == 1
    assert client.calls[0]["report_types"] == ["GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2"]
    assert client.calls[0]["processing_statuses"] == ["DONE"]
    assert client.calls[0]["marketplace_ids"] == ["ATVPDKIKX0DER"]
    manifest = store.read_report_request("settlement-1")
    assert manifest["report_id"] == "settlement-1"
    assert manifest["processing_status"] == "DONE"
    assert manifest["download_status"] == "NOT_STARTED"
    assert manifest["report_document_id"] == "doc-1"
    assert manifest["amazon_get_reports_response_item"]["reportId"] == "settlement-1"


def test_discover_available_reports_caps_lookback_to_safe_window(tmp_path) -> None:  # type: ignore[no-untyped-def]
    client = FakeReportsClient()
    store = LocalManifestStore(root_dir=tmp_path / "runtime" / "sampling")
    service = DiscoverAvailableReportsService(
        settings=_settings(tmp_path),
        sp_api_client=client,  # type: ignore[arg-type]
        manifest_store=store,
    )

    service.run(days=90, today=date(2026, 5, 14), page_size=20, max_pages=1)

    call = client.calls[0]
    assert call["created_until"] - call["created_since"] == timedelta(days=89)
    assert call["created_since"].date() == date(2026, 2, 14)


def test_discover_preserves_downloaded_manifest(tmp_path) -> None:  # type: ignore[no-untyped-def]
    client = FakeReportsClient()
    store = LocalManifestStore(root_dir=tmp_path / "runtime" / "sampling")
    store.save_report_request(
        {
            "report_id": "settlement-1",
            "report_type": "GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2",
            "marketplace_ids": ["ATVPDKIKX0DER"],
            "processing_status": "DONE",
            "download_status": "DOWNLOADED",
            "raw_file_path": "reports/raw/already-downloaded.txt",
            "report_document_id": "old-doc",
        }
    )
    service = DiscoverAvailableReportsService(
        settings=_settings(tmp_path),
        sp_api_client=client,  # type: ignore[arg-type]
        manifest_store=store,
    )

    paths = service.run(days=7, today=date(2026, 5, 14), page_size=20, max_pages=1)

    assert len(paths) == 1
    manifest = store.read_report_request("settlement-1")
    assert manifest["download_status"] == "DOWNLOADED"
    assert manifest["raw_file_path"] == "reports/raw/already-downloaded.txt"
    assert manifest["report_document_id"] == "old-doc"
