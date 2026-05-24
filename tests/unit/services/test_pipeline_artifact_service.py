from __future__ import annotations

import gzip
from pathlib import Path
from typing import Any

from seller_data_pipeline.db.repositories.pipeline_artifact_repo import PipelineArtifactRecord
from seller_data_pipeline.services.pipeline_artifact_service import (
    PipelineArtifactService,
    infer_artifact_type,
)


def test_infer_artifact_type_for_core_paths() -> None:
    assert (
        infer_artifact_type("runtime/sampling/report_requests/1.json")
        == "sp_report_request_manifest"
    )
    assert (
        infer_artifact_type("reports/raw/amazon_ads/profile/spCampaigns/a.json") == "ads_raw_report"
    )
    assert infer_artifact_type("runtime/analysis_reports/x/report.json") == "analysis_report_json"
    assert infer_artifact_type("runtime/report_delivery/x/send_result.json") == "email_send_result"


def test_save_paths_compresses_files(tmp_path: Path) -> None:
    report = tmp_path / "runtime/analysis_reports/report.json"
    report.parent.mkdir(parents=True)
    report.write_text('{"ok": true}', encoding="utf-8")

    repo = _FakeRepo()
    service = PipelineArtifactService(repo=repo)  # type: ignore[arg-type]
    result = service.save_paths(
        artifact_scope="weekly:scope",
        paths=["runtime/analysis_reports"],
        root=tmp_path,
        dry_run=False,
    )

    assert result.saved_count == 1
    assert repo.saved[0]["artifact_scope"] == "weekly:scope"
    assert gzip.decompress(repo.saved[0]["content_bytes"]) == b'{"ok": true}'


def test_restore_scope_writes_safe_relative_paths(tmp_path: Path) -> None:
    compressed = gzip.compress(b"hello")
    repo = _FakeRepo(
        records=[
            PipelineArtifactRecord(
                id=10,
                artifact_type="analysis_report_json",
                artifact_scope="weekly:scope",
                relative_path="runtime/analysis_reports/report.json",
                content_type="application/json",
                content_encoding="gzip",
                content_sha256="2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
                content_size_bytes=5,
                compressed_size_bytes=len(compressed),
                content_bytes=compressed,
                metadata_json=None,
                created_at=None,
                updated_at=None,
                expires_at=None,
                archived_at=None,
                is_deleted=False,
            )
        ]
    )
    service = PipelineArtifactService(repo=repo)  # type: ignore[arg-type]

    result = service.restore_scope(
        artifact_scope="weekly:scope",
        output_root=tmp_path,
        dry_run=False,
    )

    assert result.restored_count == 1
    assert (tmp_path / "runtime/analysis_reports/report.json").read_text() == "hello"


class _FakeRepo:
    def __init__(self, records: list[PipelineArtifactRecord] | None = None) -> None:
        self.records = records or []
        self.saved: list[dict[str, Any]] = []

    def save_artifact(self, **kwargs: Any) -> int:
        self.saved.append(kwargs)
        return len(self.saved)

    def fetch_latest_artifacts(self, **kwargs: Any) -> list[PipelineArtifactRecord]:
        return self.records

    def list_artifacts(self, **kwargs: Any) -> list[Any]:
        return []

    def mark_expired_deleted(self) -> int:
        return 0
