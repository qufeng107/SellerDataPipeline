from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class PipelineJobRunInsert:
    workflow: str
    phase: str
    execution_mode: str
    configured_trigger_type: str | None
    run_trigger_type: str | None
    run_trigger_source: str | None
    marketplace_id: str | None
    profile_id: str | None
    period_key: str | None
    stats_start: date | None
    stats_end: date | None
    request_start: date | None
    request_end: date | None
    artifact_scope: str
    azure_resource_group: str | None
    azure_job_name: str | None
    azure_execution_name: str | None
    container_app_name: str | None
    container_revision: str | None
    container_replica: str | None
    container_image: str | None
    image_tag: str | None
    git_sha: str | None
    command_line_hash: str | None
    config_snapshot_json: str | None
    started_at: datetime


@dataclass(frozen=True)
class PipelineCommandRunInsert:
    job_run_id: int
    command_index: int
    command_label: str
    script_path: str
    redacted_args_json: str | None
    args_sha256: str | None
    writes_external_or_database: bool
    status: str
    started_at: datetime


@dataclass(frozen=True)
class PipelineArtifactLinkInsert:
    job_run_id: int
    command_run_id: int | None
    artifact_id: int
    artifact_role: str
    artifact_type: str
    artifact_scope: str
    relative_path: str
    content_sha256: str
    content_size_bytes: int | None


@dataclass(frozen=True)
class PipelineTableWriteSummaryInsert:
    job_run_id: int
    command_run_id: int | None
    target_table: str
    source_system: str | None
    source_report_type: str | None
    source_report_id: str | None
    source_raw_file_path: str | None
    source_raw_file_sha256: str | None
    data_start_date: date | None
    data_end_date: date | None
    rows_read: int | None
    rows_inserted: int | None
    rows_updated: int | None
    rows_skipped: int | None
    rows_failed: int | None
    status: str
    summary_json: str | None


class PipelineJobAuditRepo:
    """Repository for structured automation job run audit records.

    Audit writes are append-oriented. Business ingestion idempotency remains in the
    normalized repositories; this repository records what actually ran and how it ended.
    """

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def insert_job_run(self, item: PipelineJobRunInsert) -> int:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO dbo.[pipeline_job_run] (
                    [workflow],
                    [phase],
                    [execution_mode],
                    [configured_trigger_type],
                    [run_trigger_type],
                    [run_trigger_source],
                    [marketplace_id],
                    [profile_id],
                    [period_key],
                    [stats_start],
                    [stats_end],
                    [request_start],
                    [request_end],
                    [artifact_scope],
                    [azure_resource_group],
                    [azure_job_name],
                    [azure_execution_name],
                    [container_app_name],
                    [container_revision],
                    [container_replica],
                    [container_image],
                    [image_tag],
                    [git_sha],
                    [command_line_hash],
                    [config_snapshot_json],
                    [started_at]
                )
                OUTPUT INSERTED.[id]
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                );
                """,
                (
                    item.workflow,
                    item.phase,
                    item.execution_mode,
                    item.configured_trigger_type,
                    item.run_trigger_type,
                    item.run_trigger_source,
                    item.marketplace_id,
                    item.profile_id,
                    item.period_key,
                    item.stats_start,
                    item.stats_end,
                    item.request_start,
                    item.request_end,
                    item.artifact_scope,
                    item.azure_resource_group,
                    item.azure_job_name,
                    item.azure_execution_name,
                    item.container_app_name,
                    item.container_revision,
                    item.container_replica,
                    item.container_image,
                    item.image_tag,
                    item.git_sha,
                    item.command_line_hash,
                    item.config_snapshot_json,
                    item.started_at.replace(tzinfo=None),
                ),
            )
            row = cursor.fetchone()
            return int(row[0]) if row is not None else 0
        finally:
            cursor.close()

    def update_job_run(
        self,
        *,
        job_run_id: int,
        status: str,
        finished_at: datetime | None,
        duration_ms: int | None,
        commands_total: int,
        commands_failed: int,
        artifact_restored_count: int,
        artifact_saved_count: int,
        artifact_skipped_count: int,
        error_type: str | None,
        error_summary: str | None,
    ) -> None:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                UPDATE dbo.[pipeline_job_run]
                SET
                    [status] = ?,
                    [finished_at] = ?,
                    [duration_ms] = ?,
                    [commands_total] = ?,
                    [commands_failed] = ?,
                    [artifact_restored_count] = ?,
                    [artifact_saved_count] = ?,
                    [artifact_skipped_count] = ?,
                    [error_type] = ?,
                    [error_summary] = ?,
                    [updated_at] = SYSUTCDATETIME()
                WHERE [id] = ?;
                """,
                (
                    status,
                    finished_at.replace(tzinfo=None) if finished_at else None,
                    duration_ms,
                    commands_total,
                    commands_failed,
                    artifact_restored_count,
                    artifact_saved_count,
                    artifact_skipped_count,
                    error_type,
                    error_summary,
                    job_run_id,
                ),
            )
        finally:
            cursor.close()

    def insert_command_run(self, item: PipelineCommandRunInsert) -> int:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO dbo.[pipeline_job_command_run] (
                    [job_run_id],
                    [command_index],
                    [command_label],
                    [script_path],
                    [redacted_args_json],
                    [args_sha256],
                    [writes_external_or_database],
                    [status],
                    [started_at]
                )
                OUTPUT INSERTED.[id]
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    item.job_run_id,
                    item.command_index,
                    item.command_label,
                    item.script_path,
                    item.redacted_args_json,
                    item.args_sha256,
                    1 if item.writes_external_or_database else 0,
                    item.status,
                    item.started_at.replace(tzinfo=None),
                ),
            )
            row = cursor.fetchone()
            return int(row[0]) if row is not None else 0
        finally:
            cursor.close()

    def update_command_run(
        self,
        *,
        command_run_id: int,
        status: str,
        exit_code: int | None,
        finished_at: datetime | None,
        duration_ms: int | None,
        rows_read: int | None = None,
        rows_inserted: int | None = None,
        rows_updated: int | None = None,
        rows_skipped: int | None = None,
        rows_failed: int | None = None,
        files_created: int | None = None,
        error_type: str | None = None,
        error_summary: str | None = None,
        output_summary_json: str | None = None,
    ) -> None:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                UPDATE dbo.[pipeline_job_command_run]
                SET
                    [status] = ?,
                    [exit_code] = ?,
                    [finished_at] = ?,
                    [duration_ms] = ?,
                    [rows_read] = ?,
                    [rows_inserted] = ?,
                    [rows_updated] = ?,
                    [rows_skipped] = ?,
                    [rows_failed] = ?,
                    [files_created] = ?,
                    [error_type] = ?,
                    [error_summary] = ?,
                    [output_summary_json] = ?,
                    [updated_at] = SYSUTCDATETIME()
                WHERE [id] = ?;
                """,
                (
                    status,
                    exit_code,
                    finished_at.replace(tzinfo=None) if finished_at else None,
                    duration_ms,
                    rows_read,
                    rows_inserted,
                    rows_updated,
                    rows_skipped,
                    rows_failed,
                    files_created,
                    error_type,
                    error_summary,
                    output_summary_json,
                    command_run_id,
                ),
            )
        finally:
            cursor.close()

    def insert_artifact_link(self, item: PipelineArtifactLinkInsert) -> None:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                IF NOT EXISTS (
                    SELECT 1
                    FROM dbo.[pipeline_job_artifact_link]
                    WHERE [job_run_id] = ?
                      AND ISNULL([command_run_id], -1) = ISNULL(?, -1)
                      AND [artifact_id] = ?
                      AND [artifact_role] = ?
                )
                BEGIN
                    INSERT INTO dbo.[pipeline_job_artifact_link] (
                        [job_run_id],
                        [command_run_id],
                        [artifact_id],
                        [artifact_role],
                        [artifact_type],
                        [artifact_scope],
                        [relative_path],
                        [content_sha256],
                        [content_size_bytes]
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                END
                """,
                (
                    item.job_run_id,
                    item.command_run_id,
                    item.artifact_id,
                    item.artifact_role,
                    item.job_run_id,
                    item.command_run_id,
                    item.artifact_id,
                    item.artifact_role,
                    item.artifact_type,
                    item.artifact_scope,
                    item.relative_path,
                    item.content_sha256,
                    item.content_size_bytes,
                ),
            )
        finally:
            cursor.close()

    def insert_table_write_summary(self, item: PipelineTableWriteSummaryInsert) -> None:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO dbo.[pipeline_job_table_write_summary] (
                    [job_run_id],
                    [command_run_id],
                    [target_table],
                    [source_system],
                    [source_report_type],
                    [source_report_id],
                    [source_raw_file_path],
                    [source_raw_file_sha256],
                    [data_start_date],
                    [data_end_date],
                    [rows_read],
                    [rows_inserted],
                    [rows_updated],
                    [rows_skipped],
                    [rows_failed],
                    [status],
                    [summary_json]
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    item.job_run_id,
                    item.command_run_id,
                    item.target_table,
                    item.source_system,
                    item.source_report_type,
                    item.source_report_id,
                    item.source_raw_file_path,
                    item.source_raw_file_sha256,
                    item.data_start_date,
                    item.data_end_date,
                    item.rows_read,
                    item.rows_inserted,
                    item.rows_updated,
                    item.rows_skipped,
                    item.rows_failed,
                    item.status,
                    item.summary_json,
                ),
            )
        finally:
            cursor.close()
