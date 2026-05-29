from __future__ import annotations

from datetime import datetime
from typing import Any

from seller_data_pipeline.db.repositories.pipeline_job_audit_repo import (
    PipelineCommandRunInsert,
    PipelineJobAuditRepo,
    PipelineJobRunInsert,
)


def test_insert_job_run_writes_pipeline_job_run() -> None:
    cursor = _FakeCursor(fetchone_values=[(321,)])
    repo = PipelineJobAuditRepo(_FakeConnection(cursor))

    job_run_id = repo.insert_job_run(
        PipelineJobRunInsert(
            workflow="weekly",
            phase="submit",
            execution_mode="execute",
            configured_trigger_type="Schedule",
            run_trigger_type="unknown",
            run_trigger_source="default:unknown",
            marketplace_id="ATVPDKIKX0DER",
            profile_id="3917953989967300",
            period_key="2026-05-16_2026-05-22",
            stats_start=None,
            stats_end=None,
            request_start=None,
            request_end=None,
            artifact_scope="weekly:scope",
            azure_resource_group="rg-amazon-ops",
            azure_job_name="sdp-weekly-submit",
            azure_execution_name="exec-1",
            container_app_name=None,
            container_revision=None,
            container_replica=None,
            container_image="ghcr.io/qufeng107/seller-data-pipeline:main",
            image_tag="main",
            git_sha="abc123",
            command_line_hash="a" * 64,
            config_snapshot_json="{}",
            started_at=datetime(2026, 5, 29),
        )
    )

    assert job_run_id == 321
    assert "INSERT INTO dbo.[pipeline_job_run]" in cursor.executed[0][0]
    assert "OUTPUT INSERTED.[id]" in cursor.executed[0][0]
    assert cursor.closed is True


def test_insert_and_update_command_run() -> None:
    cursor = _FakeCursor(fetchone_values=[(99,)])
    repo = PipelineJobAuditRepo(_FakeConnection(cursor))

    command_run_id = repo.insert_command_run(
        PipelineCommandRunInsert(
            job_run_id=1,
            command_index=1,
            command_label="Collect ready SP-API reports",
            script_path="scripts/collect_ready_reports.py",
            redacted_args_json='["--token", "***REDACTED***"]',
            args_sha256="b" * 64,
            writes_external_or_database=True,
            status="running",
            started_at=datetime(2026, 5, 29),
        )
    )
    repo.update_command_run(
        command_run_id=command_run_id,
        status="succeeded",
        exit_code=0,
        finished_at=datetime(2026, 5, 29, 0, 0, 1),
        duration_ms=1000,
        rows_read=10,
        rows_inserted=8,
        rows_updated=2,
        rows_skipped=0,
        rows_failed=0,
    )

    assert command_run_id == 99
    assert "INSERT INTO dbo.[pipeline_job_command_run]" in cursor.executed[0][0]
    assert "UPDATE dbo.[pipeline_job_command_run]" in cursor.executed[1][0]


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> _FakeCursor:
        return self._cursor


class _FakeCursor:
    def __init__(self, *, fetchone_values: list[tuple[Any, ...] | None] | None = None) -> None:
        self.fetchone_values = list(fetchone_values or [])
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self.closed = False

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        self.executed.append((sql, params))

    def fetchone(self) -> tuple[Any, ...] | None:
        if not self.fetchone_values:
            return None
        return self.fetchone_values.pop(0)

    def close(self) -> None:
        self.closed = True
