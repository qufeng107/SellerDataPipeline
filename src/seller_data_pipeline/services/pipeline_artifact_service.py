from __future__ import annotations

import gzip
import hashlib
import json
import mimetypes
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath

from seller_data_pipeline.db.repositories.pipeline_artifact_repo import (
    PipelineArtifactRecord,
    PipelineArtifactRepo,
    PipelineArtifactSummary,
)

DEFAULT_ARTIFACT_RETENTION_DAYS = 90
DEFAULT_MAX_ARTIFACT_FILE_MB = 20


@dataclass(frozen=True)
class SavedArtifact:
    artifact_id: int
    artifact_type: str
    relative_path: str
    content_size_bytes: int
    compressed_size_bytes: int
    content_sha256: str


@dataclass(frozen=True)
class ArtifactSaveResult:
    artifact_scope: str
    dry_run: bool
    scanned_count: int
    saved_artifacts: tuple[SavedArtifact, ...]
    skipped_paths: tuple[str, ...]

    @property
    def saved_count(self) -> int:
        return len(self.saved_artifacts)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped_paths)


@dataclass(frozen=True)
class RestoredArtifact:
    artifact_id: int
    artifact_type: str
    relative_path: str
    output_path: Path
    content_size_bytes: int


@dataclass(frozen=True)
class ArtifactRestoreResult:
    artifact_scope: str
    dry_run: bool
    restored_artifacts: tuple[RestoredArtifact, ...]

    @property
    def restored_count(self) -> int:
        return len(self.restored_artifacts)


@dataclass(frozen=True)
class ArtifactListResult:
    artifacts: tuple[PipelineArtifactSummary, ...]


@dataclass(frozen=True)
class ArtifactPruneResult:
    dry_run: bool
    deleted_count: int


class PipelineArtifactService:
    """Persist and restore small pipeline artifacts through Azure SQL.

    This service is a free-first bridge for Container Apps Jobs where local files do not
    survive across executions. It is intentionally small and should store only operational
    artifacts that are needed for job handoff or short-term audit.
    """

    def __init__(self, repo: PipelineArtifactRepo) -> None:
        self.repo = repo

    def save_paths(
        self,
        *,
        artifact_scope: str,
        paths: list[str | Path],
        root: str | Path = ".",
        modified_since: datetime | None = None,
        expires_days: int = DEFAULT_ARTIFACT_RETENTION_DAYS,
        max_file_mb: int = DEFAULT_MAX_ARTIFACT_FILE_MB,
        dry_run: bool = True,
    ) -> ArtifactSaveResult:
        root_path = Path(root).resolve()
        files = _expand_files(paths=paths, root=root_path)
        saved: list[SavedArtifact] = []
        skipped: list[str] = []
        expires_at = datetime.now(tz=UTC) + timedelta(days=max(1, expires_days))
        max_size_bytes = max(1, max_file_mb) * 1024 * 1024

        for file_path in files:
            try:
                stat = file_path.stat()
            except FileNotFoundError:
                skipped.append(str(file_path))
                continue
            if modified_since:
                threshold = (
                    modified_since if modified_since.tzinfo else modified_since.replace(tzinfo=UTC)
                )
                if datetime.fromtimestamp(stat.st_mtime, tz=UTC) < threshold:
                    skipped.append(_relative_path(file_path, root_path))
                    continue
            if stat.st_size > max_size_bytes:
                skipped.append(_relative_path(file_path, root_path))
                continue
            relative_path = _relative_path(file_path, root_path)
            artifact_type = infer_artifact_type(relative_path)
            content = file_path.read_bytes()
            content_sha256 = hashlib.sha256(content).hexdigest()
            compressed = gzip.compress(content, compresslevel=6)
            content_type = mimetypes.guess_type(file_path.name)[0]
            metadata_json = json.dumps(
                {
                    "source_path": str(file_path),
                    "saved_at": datetime.now(tz=UTC).isoformat(),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            if dry_run:
                artifact_id = 0
            else:
                artifact_id = self.repo.save_artifact(
                    artifact_type=artifact_type,
                    artifact_scope=artifact_scope,
                    relative_path=relative_path,
                    content_type=content_type,
                    content_encoding="gzip",
                    content_sha256=content_sha256,
                    content_size_bytes=len(content),
                    compressed_size_bytes=len(compressed),
                    content_bytes=compressed,
                    metadata_json=metadata_json,
                    expires_at=expires_at.replace(tzinfo=None),
                )
            saved.append(
                SavedArtifact(
                    artifact_id=artifact_id,
                    artifact_type=artifact_type,
                    relative_path=relative_path,
                    content_size_bytes=len(content),
                    compressed_size_bytes=len(compressed),
                    content_sha256=content_sha256,
                )
            )
        return ArtifactSaveResult(
            artifact_scope=artifact_scope,
            dry_run=dry_run,
            scanned_count=len(files),
            saved_artifacts=tuple(saved),
            skipped_paths=tuple(skipped),
        )

    def restore_scope(
        self,
        *,
        artifact_scope: str,
        output_root: str | Path = ".",
        path_prefixes: tuple[str, ...] = (),
        dry_run: bool = True,
    ) -> ArtifactRestoreResult:
        output_root_path = Path(output_root).resolve()
        records = self.repo.fetch_latest_artifacts(
            artifact_scope=artifact_scope,
            path_prefixes=tuple(_normalise_relative_path(prefix) for prefix in path_prefixes),
        )
        restored: list[RestoredArtifact] = []
        for record in records:
            output_path = _safe_output_path(output_root_path, record.relative_path)
            if not dry_run:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(_decompress_record(record))
            restored.append(
                RestoredArtifact(
                    artifact_id=record.id,
                    artifact_type=record.artifact_type,
                    relative_path=record.relative_path,
                    output_path=output_path,
                    content_size_bytes=record.content_size_bytes,
                )
            )
        return ArtifactRestoreResult(
            artifact_scope=artifact_scope,
            dry_run=dry_run,
            restored_artifacts=tuple(restored),
        )

    def list_artifacts(
        self,
        *,
        artifact_scope: str | None = None,
        artifact_type: str | None = None,
        limit: int = 100,
    ) -> ArtifactListResult:
        return ArtifactListResult(
            artifacts=tuple(
                self.repo.list_artifacts(
                    artifact_scope=artifact_scope,
                    artifact_type=artifact_type,
                    limit=limit,
                )
            )
        )

    def prune_expired(self, *, dry_run: bool = True) -> ArtifactPruneResult:
        if dry_run:
            return ArtifactPruneResult(dry_run=True, deleted_count=0)
        return ArtifactPruneResult(dry_run=False, deleted_count=self.repo.mark_expired_deleted())


def infer_artifact_type(relative_path: str) -> str:
    path = _normalise_relative_path(relative_path)
    if path.startswith("runtime/sampling/report_requests/"):
        return "sp_report_request_manifest"
    if path.startswith("runtime/sampling/ads_report_requests/"):
        return "ads_report_request_manifest"
    if path.startswith("reports/raw/amazon_ads/"):
        return "ads_raw_report"
    if path.startswith("reports/raw/amazon/"):
        return "sp_raw_report"
    if path.startswith("runtime/ingestion/"):
        return "ingestion_output"
    if path.startswith("runtime/data_coverage_audits/"):
        return "coverage_audit"
    if path.startswith("runtime/analysis_reports/") and path.endswith(".json"):
        return "analysis_report_json"
    if path.startswith("runtime/analysis_reports/") and path.endswith(".xlsx"):
        return "analysis_report_xlsx"
    if path.startswith("runtime/report_delivery/") and path.endswith("send_result.json"):
        return "email_send_result"
    if path.startswith("runtime/report_delivery/"):
        return "delivery_pack_file"
    return "pipeline_artifact"


def _expand_files(*, paths: list[str | Path], root: Path) -> list[Path]:
    files: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
        if not resolved.exists():
            continue
        if resolved.is_file():
            files.append(resolved)
            continue
        if resolved.is_dir():
            files.extend(item for item in resolved.rglob("*") if item.is_file())
    return sorted(set(files))


def _relative_path(path: Path, root: Path) -> str:
    try:
        return _normalise_relative_path(str(path.resolve().relative_to(root)))
    except ValueError as exc:
        raise ValueError(f"Artifact path must be under root={root}: {path}") from exc


def _normalise_relative_path(value: str) -> str:
    normalised = str(PurePosixPath(value.replace("\\", "/")))
    if normalised in {".", ""} or normalised.startswith("../") or normalised == "..":
        raise ValueError(f"Invalid artifact relative path: {value!r}")
    if normalised.startswith("/"):
        raise ValueError(f"Artifact relative path must not be absolute: {value!r}")
    return normalised


def _safe_output_path(output_root: Path, relative_path: str) -> Path:
    output_path = (output_root / _normalise_relative_path(relative_path)).resolve()
    try:
        output_path.relative_to(output_root)
    except ValueError as exc:
        raise ValueError(f"Unsafe artifact restore path: {relative_path}") from exc
    return output_path


def _decompress_record(record: PipelineArtifactRecord) -> bytes:
    if record.content_encoding != "gzip":
        raise ValueError(f"Unsupported artifact encoding: {record.content_encoding}")
    content = gzip.decompress(record.content_bytes)
    digest = hashlib.sha256(content).hexdigest()
    if digest != record.content_sha256:
        raise ValueError(f"Artifact sha256 mismatch for {record.relative_path}")
    return content
