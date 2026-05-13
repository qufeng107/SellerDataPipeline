from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from seller_data_pipeline.config.settings import Settings
from seller_data_pipeline.sampling.local_manifest_store import LocalManifestStore
from seller_data_pipeline.services.submit_report_requests_service import SubmitReportRequestsService


@dataclass(frozen=True)
class FakeReportRequestResult:
    report_id: str
    payload: dict[str, Any]


class FakeSpApiClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create_report(self, **kwargs: Any) -> FakeReportRequestResult:
        self.calls.append(kwargs)
        return FakeReportRequestResult(report_id="report-123", payload={"reportId": "report-123"})


def test_submit_report_request_writes_local_manifest(tmp_path: Path) -> None:
    settings = Settings(
        amazon_marketplace_id="ATVPDKIKX0DER",
        local_sampling_root=str(tmp_path / "sampling"),
    )
    client = FakeSpApiClient()
    store = LocalManifestStore(root_dir=settings.local_sampling_root)
    service = SubmitReportRequestsService(
        settings=settings,
        sp_api_client=client,  # type: ignore[arg-type]
        manifest_store=store,
    )

    manifest_path = service.run(
        report_type="GET_MERCHANT_LISTINGS_ALL_DATA",
        days=7,
        today=date(2026, 5, 13),
    )

    manifest = store.read_report_request("report-123")
    assert manifest_path.exists()
    assert manifest["report_type"] == "GET_MERCHANT_LISTINGS_ALL_DATA"
    assert manifest["marketplace_ids"] == ["ATVPDKIKX0DER"]
    assert manifest["data_start_time"] == "2026-05-06T00:00:00Z"
    assert manifest["data_end_time"] == "2026-05-13T00:00:00Z"
    assert manifest["processing_status"] == "SUBMITTED"
    assert client.calls[0]["data_start_time"].isoformat().startswith("2026-05-06")
