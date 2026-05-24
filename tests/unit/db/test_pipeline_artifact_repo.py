from __future__ import annotations

from datetime import datetime
from typing import Any

from seller_data_pipeline.db.repositories.pipeline_artifact_repo import PipelineArtifactRepo


def test_save_artifact_inserts_when_hash_not_found() -> None:
    cursor = _FakeCursor(fetchone_values=[None, (123,)])
    repo = PipelineArtifactRepo(_FakeConnection(cursor))

    artifact_id = repo.save_artifact(
        artifact_type="analysis_report_json",
        artifact_scope="weekly:scope",
        relative_path="runtime/analysis_reports/a.json",
        content_type="application/json",
        content_encoding="gzip",
        content_sha256="a" * 64,
        content_size_bytes=10,
        compressed_size_bytes=8,
        content_bytes=b"compressed",
        metadata_json=None,
        expires_at=None,
    )

    assert artifact_id == 123
    assert len(cursor.executed) == 2
    assert "SELECT TOP (1)" in cursor.executed[0][0]
    assert "INSERT INTO dbo.[pipeline_artifact_store]" in cursor.executed[1][0]
    assert cursor.closed is True


def test_fetch_latest_artifacts_filters_prefixes() -> None:
    rows = [
        {
            "id": 1,
            "artifact_type": "sp_raw_report",
            "artifact_scope": "weekly:scope",
            "relative_path": "reports/raw/a.txt",
            "content_type": "text/plain",
            "content_encoding": "gzip",
            "content_sha256": "b" * 64,
            "content_size_bytes": 12,
            "compressed_size_bytes": 10,
            "content_bytes": b"data",
            "metadata_json": None,
            "created_at": datetime(2026, 5, 24),
            "updated_at": datetime(2026, 5, 24),
            "expires_at": None,
            "archived_at": None,
            "is_deleted": False,
        }
    ]
    cursor = _FakeCursor(rows=rows)
    repo = PipelineArtifactRepo(_FakeConnection(cursor))

    result = repo.fetch_latest_artifacts(
        artifact_scope="weekly:scope",
        path_prefixes=("reports/raw",),
    )

    assert len(result) == 1
    assert result[0].relative_path == "reports/raw/a.txt"
    assert cursor.params == ("weekly:scope", "reports/raw", "reports/raw/%")


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> _FakeCursor:
        return self._cursor


class _FakeCursor:
    def __init__(
        self,
        *,
        rows: list[dict[str, Any]] | None = None,
        fetchone_values: list[tuple[Any, ...] | None] | None = None,
    ) -> None:
        self.rows = rows or []
        self.fetchone_values = list(fetchone_values or [])
        self.description = [(name,) for name in self.rows[0]] if self.rows else []
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self.params: tuple[Any, ...] | None = None
        self.closed = False
        self.rowcount = 0

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self.executed.append((sql, params))
        self.params = params

    def fetchone(self) -> tuple[Any, ...] | None:
        if not self.fetchone_values:
            return None
        return self.fetchone_values.pop(0)

    def fetchall(self) -> list[tuple[Any, ...]]:
        return [tuple(row.values()) for row in self.rows]

    def close(self) -> None:
        self.closed = True
