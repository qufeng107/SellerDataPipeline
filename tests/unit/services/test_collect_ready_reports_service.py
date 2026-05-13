from __future__ import annotations

from pathlib import Path
from typing import Any

from seller_data_pipeline.config.settings import Settings
from seller_data_pipeline.sampling.local_manifest_store import LocalManifestStore
from seller_data_pipeline.sampling.raw_report_files import RawReportFileStore
from seller_data_pipeline.services.collect_ready_reports_service import CollectReadyReportsService


class FakeDownloadedDocument:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.compression_algorithm = None
        self.raw_size_bytes = len(content)
        self.decompressed = False


class FakeSpApiClient:
    def get_report(self, *, report_id: str) -> dict[str, Any]:
        return {
            "reportId": report_id,
            "processingStatus": "DONE",
            "reportDocumentId": "doc-123",
        }

    def get_report_document(self, *, report_document_id: str) -> dict[str, Any]:
        return {
            "reportDocumentId": report_document_id,
            "url": "https://example.test/presigned",
        }

    def download_report_document(
        self,
        *,
        document_url: str,
        compression_algorithm: str | None = None,
    ) -> FakeDownloadedDocument:
        return FakeDownloadedDocument(b"sku\tprice\nABC\t9.99\n")


def test_collect_ready_report_downloads_raw_file_and_updates_manifests(tmp_path: Path) -> None:
    sampling_root = tmp_path / "sampling"
    raw_root = tmp_path / "raw"
    settings = Settings(local_sampling_root=str(sampling_root), raw_reports_root=str(raw_root))
    manifest_store = LocalManifestStore(root_dir=sampling_root)
    manifest_store.save_report_request(
        {
            "report_id": "report-123",
            "report_type": "GET_MERCHANT_LISTINGS_ALL_DATA",
            "marketplace_ids": ["ATVPDKIKX0DER"],
            "processing_status": "SUBMITTED",
            "download_status": "NOT_STARTED",
        }
    )
    service = CollectReadyReportsService(
        settings=settings,
        sp_api_client=FakeSpApiClient(),  # type: ignore[arg-type]
        manifest_store=manifest_store,
        raw_file_store=RawReportFileStore(root_dir=raw_root),
    )

    results = service.run(limit=10)

    assert len(results) == 1
    manifest = manifest_store.read_report_request("report-123")
    assert manifest["processing_status"] == "DONE"
    assert manifest["download_status"] == "DOWNLOADED"
    assert Path(manifest["raw_file_path"]).exists()
    raw_manifest_path = Path(manifest["raw_file_manifest_path"])
    raw_manifest = manifest_store._read_json(raw_manifest_path)  # noqa: SLF001
    assert raw_manifest["preview"]["header"] == ["sku", "price"]
    assert raw_manifest["preview"]["sample_rows"] == [{"sku": "ABC", "price": "9.99"}]
