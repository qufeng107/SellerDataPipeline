from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from seller_data_pipeline.db.repositories.finance_repo import rows_to_dicts


@dataclass(frozen=True)
class PipelineArtifactRecord:
    """One stored automation artifact row."""

    id: int
    artifact_type: str
    artifact_scope: str
    relative_path: str
    content_type: str | None
    content_encoding: str
    content_sha256: str
    content_size_bytes: int
    compressed_size_bytes: int
    content_bytes: bytes
    metadata_json: str | None
    created_at: datetime | None
    updated_at: datetime | None
    expires_at: datetime | None
    archived_at: datetime | None
    is_deleted: bool


@dataclass(frozen=True)
class PipelineArtifactSummary:
    """Lightweight artifact metadata without content bytes."""

    id: int
    artifact_type: str
    artifact_scope: str
    relative_path: str
    content_sha256: str
    content_size_bytes: int
    compressed_size_bytes: int
    created_at: datetime | None
    expires_at: datetime | None
    is_deleted: bool


class PipelineArtifactRepo:
    """Repository for Azure SQL backed small artifact persistence.

    The repository intentionally stores compressed bytes in SQL only for the v1
    free-first automation profile. It should not become the long-term large-file store.
    """

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def save_artifact(
        self,
        *,
        artifact_type: str,
        artifact_scope: str,
        relative_path: str,
        content_type: str | None,
        content_encoding: str,
        content_sha256: str,
        content_size_bytes: int,
        compressed_size_bytes: int,
        content_bytes: bytes,
        metadata_json: str | None,
        expires_at: datetime | None,
    ) -> int:
        """Insert an artifact version or refresh an identical active artifact.

        A changed file creates a new row. An identical file under the same scope/path/hash
        updates metadata and expiry without duplicating content.
        """

        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                SELECT TOP (1) [id]
                FROM dbo.[pipeline_artifact_store]
                WHERE [artifact_scope] = ?
                  AND [relative_path] = ?
                  AND [content_sha256] = ?
                  AND [is_deleted] = 0
                ORDER BY [created_at] DESC, [id] DESC;
                """,
                (artifact_scope, relative_path, content_sha256),
            )
            row = cursor.fetchone()
            if row is not None:
                artifact_id = int(row[0])
                cursor.execute(
                    """
                    UPDATE dbo.[pipeline_artifact_store]
                    SET
                        [artifact_type] = ?,
                        [content_type] = ?,
                        [content_encoding] = ?,
                        [content_size_bytes] = ?,
                        [compressed_size_bytes] = ?,
                        [metadata_json] = ?,
                        [expires_at] = ?,
                        [updated_at] = SYSUTCDATETIME()
                    WHERE [id] = ?;
                    """,
                    (
                        artifact_type,
                        content_type,
                        content_encoding,
                        content_size_bytes,
                        compressed_size_bytes,
                        metadata_json,
                        expires_at,
                        artifact_id,
                    ),
                )
                return artifact_id

            cursor.execute(
                """
                INSERT INTO dbo.[pipeline_artifact_store] (
                    [artifact_type],
                    [artifact_scope],
                    [relative_path],
                    [content_type],
                    [content_encoding],
                    [content_sha256],
                    [content_size_bytes],
                    [compressed_size_bytes],
                    [content_bytes],
                    [metadata_json],
                    [expires_at]
                )
                OUTPUT INSERTED.[id]
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    artifact_type,
                    artifact_scope,
                    relative_path,
                    content_type,
                    content_encoding,
                    content_sha256,
                    content_size_bytes,
                    compressed_size_bytes,
                    content_bytes,
                    metadata_json,
                    expires_at,
                ),
            )
            inserted = cursor.fetchone()
            return int(inserted[0]) if inserted is not None else 0
        finally:
            cursor.close()

    def fetch_latest_artifacts(
        self,
        *,
        artifact_scope: str,
        path_prefixes: tuple[str, ...] = (),
    ) -> list[PipelineArtifactRecord]:
        """Fetch latest active artifact version per relative path for one scope."""

        prefix_sql = ""
        params: list[Any] = [artifact_scope]
        normalized_prefixes = tuple(prefix.rstrip("/") for prefix in path_prefixes if prefix)
        if normalized_prefixes:
            prefix_sql = " AND (" + " OR ".join(
                "[relative_path] = ? OR [relative_path] LIKE ?" for _ in normalized_prefixes
            ) + ")"
            for prefix in normalized_prefixes:
                params.extend([prefix, f"{prefix}/%"])

        cursor = self.connection.cursor()
        try:
            cursor.execute(
                f"""
                WITH ranked AS (
                    SELECT
                        [id],
                        [artifact_type],
                        [artifact_scope],
                        [relative_path],
                        [content_type],
                        [content_encoding],
                        [content_sha256],
                        [content_size_bytes],
                        [compressed_size_bytes],
                        [content_bytes],
                        [metadata_json],
                        [created_at],
                        [updated_at],
                        [expires_at],
                        [archived_at],
                        [is_deleted],
                        ROW_NUMBER() OVER (
                            PARTITION BY [relative_path]
                            ORDER BY [created_at] DESC, [id] DESC
                        ) AS [rn]
                    FROM dbo.[pipeline_artifact_store]
                    WHERE [artifact_scope] = ?
                      AND [is_deleted] = 0
                      AND ([expires_at] IS NULL OR [expires_at] > SYSUTCDATETIME())
                      {prefix_sql}
                )
                SELECT
                    [id],
                    [artifact_type],
                    [artifact_scope],
                    [relative_path],
                    [content_type],
                    [content_encoding],
                    [content_sha256],
                    [content_size_bytes],
                    [compressed_size_bytes],
                    [content_bytes],
                    [metadata_json],
                    [created_at],
                    [updated_at],
                    [expires_at],
                    [archived_at],
                    [is_deleted]
                FROM ranked
                WHERE [rn] = 1
                ORDER BY [relative_path];
                """,
                tuple(params),
            )
            return [_record_from_row(row) for row in rows_to_dicts(cursor)]
        finally:
            cursor.close()

    def list_artifacts(
        self,
        *,
        artifact_scope: str | None = None,
        artifact_type: str | None = None,
        limit: int = 100,
    ) -> list[PipelineArtifactSummary]:
        where = ["[is_deleted] = 0"]
        filter_params: list[Any] = []
        if artifact_scope:
            where.append("[artifact_scope] = ?")
            filter_params.append(artifact_scope)
        if artifact_type:
            where.append("[artifact_type] = ?")
            filter_params.append(artifact_type)
        params: list[Any] = [max(1, limit), *filter_params]
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                f"""
                SELECT TOP (?)
                    [id],
                    [artifact_type],
                    [artifact_scope],
                    [relative_path],
                    [content_sha256],
                    [content_size_bytes],
                    [compressed_size_bytes],
                    [created_at],
                    [expires_at],
                    [is_deleted]
                FROM dbo.[pipeline_artifact_store]
                WHERE {' AND '.join(where)}
                ORDER BY [created_at] DESC, [id] DESC;
                """,
                tuple(params),
            )
            return [_summary_from_row(row) for row in rows_to_dicts(cursor)]
        finally:
            cursor.close()

    def mark_expired_deleted(self) -> int:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                UPDATE dbo.[pipeline_artifact_store]
                SET
                    [is_deleted] = 1,
                    [updated_at] = SYSUTCDATETIME()
                WHERE [is_deleted] = 0
                  AND [expires_at] IS NOT NULL
                  AND [expires_at] <= SYSUTCDATETIME();
                """,
                (),
            )
            return int(getattr(cursor, "rowcount", 0) or 0)
        finally:
            cursor.close()


def _record_from_row(row: dict[str, Any]) -> PipelineArtifactRecord:
    return PipelineArtifactRecord(
        id=int(row.get("id") or 0),
        artifact_type=str(row.get("artifact_type") or ""),
        artifact_scope=str(row.get("artifact_scope") or ""),
        relative_path=str(row.get("relative_path") or ""),
        content_type=str(row["content_type"]) if row.get("content_type") is not None else None,
        content_encoding=str(row.get("content_encoding") or "gzip"),
        content_sha256=str(row.get("content_sha256") or ""),
        content_size_bytes=int(row.get("content_size_bytes") or 0),
        compressed_size_bytes=int(row.get("compressed_size_bytes") or 0),
        content_bytes=bytes(row.get("content_bytes") or b""),
        metadata_json=str(row["metadata_json"]) if row.get("metadata_json") is not None else None,
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        expires_at=row.get("expires_at"),
        archived_at=row.get("archived_at"),
        is_deleted=bool(row.get("is_deleted")),
    )


def _summary_from_row(row: dict[str, Any]) -> PipelineArtifactSummary:
    return PipelineArtifactSummary(
        id=int(row.get("id") or 0),
        artifact_type=str(row.get("artifact_type") or ""),
        artifact_scope=str(row.get("artifact_scope") or ""),
        relative_path=str(row.get("relative_path") or ""),
        content_sha256=str(row.get("content_sha256") or ""),
        content_size_bytes=int(row.get("content_size_bytes") or 0),
        compressed_size_bytes=int(row.get("compressed_size_bytes") or 0),
        created_at=row.get("created_at"),
        expires_at=row.get("expires_at"),
        is_deleted=bool(row.get("is_deleted")),
    )
