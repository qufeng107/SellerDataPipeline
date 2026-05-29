from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from seller_data_pipeline.db.repositories.pipeline_job_audit_repo import (
    PipelineArtifactLinkInsert,
    PipelineCommandRunInsert,
    PipelineJobAuditRepo,
    PipelineJobRunInsert,
    PipelineTableWriteSummaryInsert,
)
from seller_data_pipeline.services.automation_schedule_service import AutomationCommand
from seller_data_pipeline.services.pipeline_artifact_service import (
    ArtifactRestoreResult,
    ArtifactSaveResult,
    RestoredArtifact,
    SavedArtifact,
)

logger = logging.getLogger(__name__)

_SECRET_NAME_RE = re.compile(
    r"(password|passwd|pwd|secret|token|refresh|credential|client[-_]?secret|"
    r"smtp[-_]?password|key)",
    re.IGNORECASE,
)
_SENSITIVE_VALUE_RE = re.compile(
    r"(?i)(password|passwd|pwd|secret|token|refresh[_-]?token|client[_-]?secret|"
    r"api[_-]?key)\s*[:=]\s*[^\s,;]+"
)
_MAX_ERROR_CHARS = 4000
_MAX_JSON_CHARS = 20000


@dataclass(frozen=True)
class AutomationAuditWindow:
    period_key: str | None
    stats_start: date | None
    stats_end: date | None
    request_start: date | None
    request_end: date | None


@dataclass(frozen=True)
class AutomationAuditContext:
    workflow: str
    phase: str
    execution_mode: str
    configured_trigger_type: str | None
    run_trigger_type: str | None
    run_trigger_source: str | None
    marketplace_id: str | None
    profile_id: str | None
    artifact_scope: str
    window: AutomationAuditWindow
    command_line_hash: str | None
    config_snapshot_json: str | None
    started_at: datetime


@dataclass(frozen=True)
class CommandAuditHandle:
    command_run_id: int
    command_index: int
    started_at: datetime


class PipelineJobAuditService:
    """Best-effort structured audit writer for automation stage runs.

    The service is intentionally non-critical: if the audit tables are missing or an audit write
    fails, the business command should continue and the problem is logged to console/Log Analytics.
    """

    def __init__(self, repo: PipelineJobAuditRepo, *, enabled: bool = True) -> None:
        self.repo = repo
        self.enabled = enabled
        self.job_run_id: int | None = None
        self.command_run_ids: dict[int, int] = {}
        self._disabled_reason: str | None = None

    @property
    def is_active(self) -> bool:
        return self.enabled and self.job_run_id is not None and self._disabled_reason is None

    def start_run(self, context: AutomationAuditContext) -> int | None:
        if not self.enabled:
            return None
        try:
            self.job_run_id = self.repo.insert_job_run(
                PipelineJobRunInsert(
                    workflow=context.workflow,
                    phase=context.phase,
                    execution_mode=context.execution_mode,
                    configured_trigger_type=context.configured_trigger_type,
                    run_trigger_type=context.run_trigger_type,
                    run_trigger_source=context.run_trigger_source,
                    marketplace_id=context.marketplace_id,
                    profile_id=context.profile_id,
                    period_key=context.window.period_key,
                    stats_start=context.window.stats_start,
                    stats_end=context.window.stats_end,
                    request_start=context.window.request_start,
                    request_end=context.window.request_end,
                    artifact_scope=context.artifact_scope,
                    azure_resource_group=_first_env(
                        "SDP_AZURE_RESOURCE_GROUP", "AZURE_RESOURCE_GROUP", "RESOURCE_GROUP"
                    ),
                    azure_job_name=_first_env(
                        "SDP_AZURE_JOB_NAME",
                        "AZURE_CONTAINERAPP_JOB_NAME",
                        "CONTAINER_APP_JOB_NAME",
                        "CONTAINERAPP_JOB_NAME",
                    ),
                    azure_execution_name=_first_env(
                        "SDP_AZURE_JOB_EXECUTION_NAME",
                        "AZURE_CONTAINERAPP_JOB_EXECUTION_NAME",
                        "CONTAINER_APP_JOB_EXECUTION_NAME",
                        "CONTAINERAPP_JOB_EXECUTION_NAME",
                    ),
                    container_app_name=_first_env(
                        "SDP_CONTAINER_APP_NAME", "CONTAINER_APP_NAME", "CONTAINER_APP"
                    ),
                    container_revision=_first_env(
                        "SDP_CONTAINER_REVISION", "CONTAINER_APP_REVISION", "K_REVISION"
                    ),
                    container_replica=_first_env(
                        "SDP_CONTAINER_REPLICA", "CONTAINER_APP_REPLICA", "HOSTNAME"
                    ),
                    container_image=_first_env("SDP_CONTAINER_IMAGE", "CONTAINER_IMAGE"),
                    image_tag=_first_env("SDP_IMAGE_TAG", "IMAGE_TAG"),
                    git_sha=_first_env("SDP_GIT_SHA", "GITHUB_SHA", "COMMIT_SHA"),
                    command_line_hash=context.command_line_hash,
                    config_snapshot_json=context.config_snapshot_json,
                    started_at=context.started_at,
                )
            )
            return self.job_run_id
        except Exception as exc:  # pragma: no cover - defensive cloud path
            self._disable_after_error("start_run", exc)
            return None

    def command_started(
        self,
        command_index: int,
        command: AutomationCommand,
        started_at: datetime,
    ) -> CommandAuditHandle | None:
        if not self.is_active or self.job_run_id is None:
            return None
        try:
            command_run_id = self.repo.insert_command_run(
                PipelineCommandRunInsert(
                    job_run_id=self.job_run_id,
                    command_index=command_index,
                    command_label=command.label,
                    script_path=command.argv[0] if command.argv else "",
                    redacted_args_json=_to_limited_json(_redact_argv(command.argv)),
                    args_sha256=_sha256_json(list(command.argv)),
                    writes_external_or_database=command.writes_external_or_database,
                    status="running",
                    started_at=started_at,
                )
            )
            self.command_run_ids[command_index] = command_run_id
            return CommandAuditHandle(
                command_run_id=command_run_id,
                command_index=command_index,
                started_at=started_at,
            )
        except Exception as exc:  # pragma: no cover - defensive cloud path
            self._disable_after_error("command_started", exc)
            return None

    def command_finished(
        self,
        handle: CommandAuditHandle | None,
        exit_code: int | None,
        finished_at: datetime,
        output_summary: dict[str, Any] | None = None,
        error: BaseException | None = None,
    ) -> None:
        if not self.is_active or handle is None:
            return
        status = _command_status(exit_code=exit_code, output_summary=output_summary, error=error)
        raw_error_summary = str(error) if error else _error_summary_from(output_summary)
        error_summary = _redact_text(raw_error_summary) if raw_error_summary else None
        duration_ms = _duration_ms(handle.started_at, finished_at)
        metrics = _metrics_from_summary(output_summary or {})
        try:
            self.repo.update_command_run(
                command_run_id=handle.command_run_id,
                status=status,
                exit_code=exit_code,
                finished_at=finished_at,
                duration_ms=duration_ms,
                rows_read=metrics.get("rows_read"),
                rows_inserted=metrics.get("rows_inserted"),
                rows_updated=metrics.get("rows_updated"),
                rows_skipped=metrics.get("rows_skipped"),
                rows_failed=metrics.get("rows_failed"),
                files_created=metrics.get("files_created"),
                error_type=type(error).__name__ if error else None,
                error_summary=_limit_text(error_summary) if error_summary else None,
                output_summary_json=_to_limited_json(_redact_value(output_summary))
                if output_summary
                else None,
            )
        except Exception as exc:  # pragma: no cover - defensive cloud path
            self._disable_after_error("command_finished", exc)

    def link_restored_artifacts(self, result: ArtifactRestoreResult) -> None:
        if not self.is_active or self.job_run_id is None:
            return
        for artifact in result.restored_artifacts:
            self._insert_artifact_link(
                _restored_to_link(self.job_run_id, result.artifact_scope, artifact)
            )

    def link_saved_artifacts(self, result: ArtifactSaveResult) -> None:
        if not self.is_active or self.job_run_id is None:
            return
        for artifact in result.saved_artifacts:
            if artifact.artifact_id <= 0:
                continue
            role = _artifact_role(artifact.artifact_type)
            self._insert_artifact_link(
                _saved_to_link(self.job_run_id, result.artifact_scope, artifact, role)
            )

    def insert_table_write_summaries_from_saved_artifacts(
        self,
        *,
        save_result: ArtifactSaveResult,
        root: str | Path = ".",
    ) -> int:
        if not self.is_active or self.job_run_id is None:
            return 0
        root_path = Path(root).resolve()
        inserted = 0
        for artifact in save_result.saved_artifacts:
            if artifact.artifact_type != "ingestion_output" or not artifact.relative_path.endswith(
                ".json"
            ):
                continue
            path = (root_path / artifact.relative_path).resolve()
            if not _is_relative_to(path, root_path) or not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            for summary in _table_write_summaries_from_payload(payload):
                command_run_id = _find_command_for_table_summary(self.command_run_ids, summary)
                item = PipelineTableWriteSummaryInsert(
                    job_run_id=self.job_run_id,
                    command_run_id=command_run_id,
                    target_table=summary["target_table"],
                    source_system=summary.get("source_system"),
                    source_report_type=summary.get("source_report_type"),
                    source_report_id=summary.get("source_report_id"),
                    source_raw_file_path=summary.get("source_raw_file_path"),
                    source_raw_file_sha256=summary.get("source_raw_file_sha256"),
                    data_start_date=None,
                    data_end_date=None,
                    rows_read=_as_int(summary.get("rows_read")),
                    rows_inserted=_as_int(summary.get("rows_inserted")),
                    rows_updated=_as_int(summary.get("rows_updated")),
                    rows_skipped=_as_int(summary.get("rows_skipped")),
                    rows_failed=_as_int(summary.get("rows_failed")),
                    status=summary.get("status") or "succeeded",
                    summary_json=_to_limited_json(_redact_value(summary)),
                )
                try:
                    self.repo.insert_table_write_summary(item)
                    inserted += 1
                except Exception as exc:  # pragma: no cover - defensive cloud path
                    self._disable_after_error("insert_table_write_summary", exc)
                    return inserted
        return inserted

    def finish_run(
        self,
        *,
        status: str,
        finished_at: datetime,
        started_at: datetime,
        commands_total: int,
        commands_failed: int,
        artifact_restored_count: int,
        artifact_saved_count: int,
        artifact_skipped_count: int,
        error: BaseException | None = None,
        error_summary: str | None = None,
    ) -> None:
        if not self.is_active or self.job_run_id is None:
            return
        summary = error_summary or (str(error) if error else None)
        try:
            self.repo.update_job_run(
                job_run_id=self.job_run_id,
                status=status,
                finished_at=finished_at,
                duration_ms=_duration_ms(started_at, finished_at),
                commands_total=commands_total,
                commands_failed=commands_failed,
                artifact_restored_count=artifact_restored_count,
                artifact_saved_count=artifact_saved_count,
                artifact_skipped_count=artifact_skipped_count,
                error_type=type(error).__name__ if error else None,
                error_summary=_limit_text(_redact_text(summary or "")) if summary else None,
            )
        except Exception as exc:  # pragma: no cover - defensive cloud path
            self._disable_after_error("finish_run", exc)

    def write_stage_result_artifact(
        self,
        *,
        path: str | Path,
        status: str,
        workflow: str,
        phase: str,
        artifact_scope: str,
        started_at: datetime,
        finished_at: datetime,
        commands_total: int,
        commands_failed: int,
        artifact_restored_count: int,
        artifact_saved_count: int,
        artifact_skipped_count: int,
    ) -> None:
        payload = {
            "job_run_id": self.job_run_id,
            "workflow": workflow,
            "phase": phase,
            "artifact_scope": artifact_scope,
            "status": status,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_ms": _duration_ms(started_at, finished_at),
            "commands_total": commands_total,
            "commands_failed": commands_failed,
            "artifact_restored_count": artifact_restored_count,
            "artifact_saved_count": artifact_saved_count,
            "artifact_skipped_count": artifact_skipped_count,
            "audit_disabled_reason": self._disabled_reason,
        }
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _insert_artifact_link(self, item: PipelineArtifactLinkInsert) -> None:
        try:
            self.repo.insert_artifact_link(item)
        except Exception as exc:  # pragma: no cover - defensive cloud path
            self._disable_after_error("insert_artifact_link", exc)

    def _disable_after_error(self, operation: str, exc: BaseException) -> None:
        self._disabled_reason = f"{operation}: {type(exc).__name__}: {exc}"
        logger.warning("Pipeline job audit write disabled after %s failed: %s", operation, exc)


# The summary parser is deliberately permissive. It only extracts safe operational counts from
# known local JSON artifacts and never blocks the main pipeline if a file shape changes.
def _table_write_summaries_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    upsert = payload.get("upsert_result") if isinstance(payload, dict) else None
    dry_run = payload.get("dry_run_result") if isinstance(payload, dict) else None
    base = {
        "source_system": _source_system_from_payload(payload),
        "source_raw_file_path": _source_raw_path_from_payload(payload),
        "status": _status_for_table_summary(payload),
    }
    if isinstance(upsert, dict):
        if isinstance(upsert.get("table_result"), dict):
            summaries.append(_summary_from_table_result(upsert["table_result"], base))
        for table_result in upsert.get("table_results") or []:
            if isinstance(table_result, dict):
                summaries.append(_summary_from_table_result(table_result, base))
    if not summaries and isinstance(dry_run, dict):
        # Blocked/dry-run summaries still matter for audit because they explain why no DB write
        # occurred. They use prepared row counts as rows_read and zero write counts.
        for report in _iter_dry_run_report_results(dry_run):
            if not isinstance(report, dict):
                continue
            target_table = report.get("target_table")
            if not target_table:
                continue
            summaries.append(
                {
                    **base,
                    "target_table": target_table,
                    "source_report_type": report.get("report_type"),
                    "source_raw_file_path": (
                        report.get("raw_file_path") or base["source_raw_file_path"]
                    ),
                    "rows_read": _as_int(report.get("parsed_row_count")),
                    "rows_inserted": 0,
                    "rows_updated": 0,
                    "rows_skipped": _as_int(report.get("prepared_row_count")),
                    "rows_failed": None,
                    "status": "blocked" if payload.get("requires_review") else base["status"],
                }
            )
    return [summary for summary in summaries if summary.get("target_table")]


def _summary_from_table_result(
    table_result: dict[str, Any], base: dict[str, Any]
) -> dict[str, Any]:
    return {
        **base,
        "target_table": table_result.get("table_name") or table_result.get("target_table"),
        "source_report_type": table_result.get("report_type") or table_result.get("report_type_id"),
        "rows_read": _as_int(table_result.get("attempted_rows")),
        "rows_inserted": _as_int(table_result.get("inserted_rows")),
        "rows_updated": _as_int(table_result.get("updated_rows")),
        "rows_skipped": _as_int(table_result.get("skipped_rows")),
        "rows_failed": 0,
    }


def _iter_dry_run_report_results(dry_run: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for key in ("report_result", "daily_result", "asin_result"):
        value = dry_run.get(key)
        if isinstance(value, dict):
            results.append(value)
    for key in ("report_results", "table_results"):
        value = dry_run.get(key)
        if isinstance(value, list):
            results.extend(item for item in value if isinstance(item, dict))
    return results


def _source_system_from_payload(payload: dict[str, Any]) -> str | None:
    workflow_name = str(payload.get("workflow_name") or "")
    if "ads" in workflow_name:
        return "amazon_ads"
    if "sp_api" in workflow_name or workflow_name:
        return "sp_api_reports"
    return None


def _source_raw_path_from_payload(payload: dict[str, Any]) -> str | None:
    dry_run = payload.get("dry_run_result")
    if not isinstance(dry_run, dict):
        return None
    report = dry_run.get("report_result")
    if isinstance(report, dict) and report.get("raw_file_path"):
        return str(report["raw_file_path"])
    for item in _iter_dry_run_report_results(dry_run):
        raw = item.get("raw_file_path") if isinstance(item, dict) else None
        if raw:
            return str(raw)
    return None


def _status_for_table_summary(payload: dict[str, Any]) -> str:
    if payload.get("requires_review"):
        return "blocked"
    status = str(payload.get("status") or "")
    if "failed" in status:
        return "failed"
    if "blocked" in status or "requires_review" in status:
        return "blocked"
    return "succeeded"


def _find_command_for_table_summary(
    command_run_ids: dict[int, int], summary: dict[str, Any]
) -> int | None:
    # v1 does not have a reliable summary-file to command-index map. Keep the run-level lineage
    # rather than guess incorrectly. Command-level mapping can be added later by passing expected
    # JSON output paths into each AutomationCommand.
    _ = (command_run_ids, summary)
    return None


def _restored_to_link(
    job_run_id: int, artifact_scope: str, artifact: RestoredArtifact
) -> PipelineArtifactLinkInsert:
    return PipelineArtifactLinkInsert(
        job_run_id=job_run_id,
        command_run_id=None,
        artifact_id=artifact.artifact_id,
        artifact_role="restored_input",
        artifact_type=artifact.artifact_type,
        artifact_scope=artifact_scope,
        relative_path=artifact.relative_path,
        content_sha256="0" * 64,
        content_size_bytes=artifact.content_size_bytes,
    )


def _saved_to_link(
    job_run_id: int, artifact_scope: str, artifact: SavedArtifact, artifact_role: str
) -> PipelineArtifactLinkInsert:
    return PipelineArtifactLinkInsert(
        job_run_id=job_run_id,
        command_run_id=None,
        artifact_id=artifact.artifact_id,
        artifact_role=artifact_role,
        artifact_type=artifact.artifact_type,
        artifact_scope=artifact_scope,
        relative_path=artifact.relative_path,
        content_sha256=artifact.content_sha256,
        content_size_bytes=artifact.content_size_bytes,
    )


def _artifact_role(artifact_type: str) -> str:
    if artifact_type in {"sp_raw_report", "ads_raw_report"}:
        return "raw_report"
    if artifact_type.endswith("request_manifest"):
        return "request_manifest"
    if artifact_type == "ingestion_output":
        return "ingestion_output"
    if artifact_type == "coverage_audit":
        return "coverage_audit"
    if artifact_type.startswith("analysis_report"):
        return "analysis_report"
    if artifact_type == "email_send_result":
        return "email_send_result"
    if artifact_type == "delivery_pack_file":
        return "report_delivery_pack"
    if artifact_type == "automation_audit":
        return "automation_audit"
    return "saved_output"


def _command_status(
    *, exit_code: int | None, output_summary: dict[str, Any] | None, error: BaseException | None
) -> str:
    if error is not None:
        return "failed"
    if exit_code is None:
        return "skipped"
    if exit_code == 0:
        return "succeeded"
    summary_status = str((output_summary or {}).get("status") or "").lower()
    if "review" in summary_status or "blocked" in summary_status:
        return "blocked"
    return "failed"


def _error_summary_from(output_summary: dict[str, Any] | None) -> str | None:
    if not output_summary:
        return None
    for key in ("message", "error", "error_summary", "error_detail"):
        value = output_summary.get(key)
        if value:
            return str(value)
    return None


def _metrics_from_summary(payload: dict[str, Any]) -> dict[str, int | None]:
    upsert = payload.get("upsert_result") if isinstance(payload, dict) else None
    if isinstance(upsert, dict):
        return {
            "rows_read": _as_int(upsert.get("attempted_rows")),
            "rows_inserted": _as_int(upsert.get("inserted_rows")),
            "rows_updated": _as_int(upsert.get("updated_rows")),
            "rows_skipped": _as_int(upsert.get("skipped_rows")),
            "rows_failed": 0,
            "files_created": None,
        }
    dry_run = payload.get("dry_run_result") if isinstance(payload, dict) else None
    if isinstance(dry_run, dict):
        return {
            "rows_read": _as_int(dry_run.get("parsed_row_count")),
            "rows_inserted": 0,
            "rows_updated": 0,
            "rows_skipped": _as_int(dry_run.get("skipped_report_count")),
            "rows_failed": None,
            "files_created": _as_int(dry_run.get("preview_file_count")),
        }
    return {}


def build_config_snapshot(
    *,
    workflow: str,
    phase: str,
    reference_date: date,
    week_start: date | None,
    month: str | None,
    send_email: bool,
    force_resend: bool,
    continue_on_error: bool,
    skip_artifact_store: bool,
    email_to: tuple[str, ...],
) -> str:
    return _to_limited_json(
        {
            "workflow": workflow,
            "phase": phase,
            "reference_date": reference_date.isoformat(),
            "week_start": week_start.isoformat() if week_start else None,
            "month": month,
            "send_email": send_email,
            "force_resend": force_resend,
            "continue_on_error": continue_on_error,
            "skip_artifact_store": skip_artifact_store,
            "email_to_count": len(email_to),
        }
    ) or "{}"


def command_line_hash(argv: list[str]) -> str:
    return hashlib.sha256(json.dumps(argv, ensure_ascii=False).encode("utf-8")).hexdigest()


def resolve_trigger_value(value: str | None, *, env_name: str) -> tuple[str | None, str | None]:
    if value:
        return value, "cli"
    env_value = os.getenv(env_name)
    if env_value:
        return env_value, f"env:{env_name}"
    return None, "default:unknown"


def _redact_argv(argv: tuple[str, ...]) -> list[str]:
    redacted: list[str] = []
    previous_is_secret = False
    for item in argv:
        if previous_is_secret:
            redacted.append("***REDACTED***")
            previous_is_secret = False
            continue
        redacted.append("***REDACTED***" if _looks_secret_value(item) else item)
        if item.startswith("--") and _SECRET_NAME_RE.search(item):
            previous_is_secret = True
    return redacted


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _SECRET_NAME_RE.search(str(key)):
                redacted[str(key)] = "***REDACTED***"
            else:
                redacted[str(key)] = _redact_value(item)
        return redacted
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _redact_text(value: str) -> str:
    return _SENSITIVE_VALUE_RE.sub(_redact_sensitive_match, value)


def _redact_sensitive_match(match: re.Match[str]) -> str:
    text = match.group(0)
    separator = "=" if "=" in text else ":"
    return text.split(separator, 1)[0] + separator + "***REDACTED***"


def _looks_secret_value(value: str) -> bool:
    return bool(_SENSITIVE_VALUE_RE.search(value))


def _to_limited_json(value: Any) -> str | None:
    if value is None:
        return None
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    if len(text) > _MAX_JSON_CHARS:
        return text[: _MAX_JSON_CHARS - 20] + '..."__truncated__"'
    return text


def _sha256_json(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _duration_ms(started_at: datetime, finished_at: datetime) -> int:
    return max(0, int((finished_at - started_at).total_seconds() * 1000))


def _limit_text(value: str) -> str:
    return value[:_MAX_ERROR_CHARS]


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value not in (None, ""):
            return value
    return None


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


__all__ = [
    "AutomationAuditContext",
    "AutomationAuditWindow",
    "PipelineJobAuditService",
    "build_config_snapshot",
    "command_line_hash",
    "resolve_trigger_value",
]
