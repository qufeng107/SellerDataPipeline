from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from seller_data_pipeline.db.connection import get_connection
from seller_data_pipeline.db.repositories.ads_repo import (
    AdsRepo,
    AdsUpsertRunResult,
    AdsUpsertTableResult,
)
from seller_data_pipeline.ingestion.ads_ingestion_dry_run import (
    AdsIngestionDryRunResult,
    AdsIngestionDryRunService,
)
from seller_data_pipeline.ingestion.ads_table_mapping import (
    get_ads_target_table_spec,
    read_jsonl,
)


@dataclass(frozen=True)
class AdsIngestionRunResult:
    workflow_name: str
    mode: str
    status: str
    requires_review: bool
    dry_run_result: AdsIngestionDryRunResult
    upsert_result: AdsUpsertRunResult | None
    sync_run_id: int | None
    message: str

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(asdict(self), ensure_ascii=False, default=str))


class AdsIngestionService:
    """Run guarded Amazon Ads ingestion.

    By default callers should run this in dry-run mode. Real Azure SQL writes are only performed
    when execute=True, after the dry-run guard has produced DB-ready preview rows with no schema
    review requirement.
    """

    def __init__(
        self,
        *,
        raw_reports_root: str | Path,
        output_root: str | Path = "runtime/ingestion/amazon_ads",
    ) -> None:
        self.dry_run_service = AdsIngestionDryRunService(
            raw_reports_root=raw_reports_root,
            output_root=output_root,
        )

    def run(
        self,
        *,
        profile_id: str,
        report_type_ids: list[str] | None = None,
        marketplace_id: str | None = None,
        execute: bool = False,
        fail_on_review: bool = True,
    ) -> AdsIngestionRunResult:
        dry_run_result = self.dry_run_service.prepare(
            profile_id=profile_id,
            report_type_ids=report_type_ids,
            marketplace_id=marketplace_id,
            fail_on_review=fail_on_review,
        )
        if dry_run_result.requires_review:
            return AdsIngestionRunResult(
                workflow_name="amazon_ads_ingestion",
                mode="execute" if execute else "dry_run",
                status="blocked_requires_review",
                requires_review=True,
                dry_run_result=dry_run_result,
                upsert_result=None,
                sync_run_id=None,
                message="Schema/table validation requires manual review; database write skipped.",
            )
        if not execute:
            return AdsIngestionRunResult(
                workflow_name="amazon_ads_ingestion",
                mode="dry_run",
                status="dry_run_success",
                requires_review=False,
                dry_run_result=dry_run_result,
                upsert_result=None,
                sync_run_id=None,
                message="Dry run completed; database write skipped because --execute was not set.",
            )

        with get_connection(autocommit=False) as conn:
            repo = AdsRepo(conn)
            started_at = _utc_now_iso()
            initial_audit_event = dict(dry_run_result.task_audit_event)
            initial_audit_event.update(
                {
                    "workflow_name": "amazon_ads_ingestion",
                    "job_name": "ingest_ads_reports",
                    "task_type": "ingestion_upsert",
                    "run_mode": "azure_sql_write",
                    "status": "running",
                    "started_at": started_at,
                    "finished_at": None,
                    "rows_written": 0,
                    "message": "Amazon Ads ingestion started after dry-run guard passed.",
                }
            )
            sync_run_id = repo.insert_sync_run_log(initial_audit_event)
            repo.commit()
            try:
                table_results = self._upsert_preview_rows(
                    repo=repo,
                    dry_run_result=dry_run_result,
                    source_run_id=sync_run_id,
                )
                schema_events = _load_schema_validation_events(dry_run_result.output_dir)
                repo.insert_schema_validation_events(schema_events, source_run_id=sync_run_id)
                upsert_result = AdsUpsertRunResult(
                    table_results=tuple(table_results),
                    sync_run_id=sync_run_id,
                )
                final_audit_event = build_final_audit_event(
                    dry_run_result=dry_run_result,
                    upsert_result=upsert_result,
                    started_at=started_at,
                    status="success",
                    message="Amazon Ads rows upserted successfully.",
                )
                repo.update_sync_run_log(sync_run_id, final_audit_event)
                repo.commit()
            except Exception as exc:
                _rollback_safely(conn)
                failure_event = build_failure_audit_event(
                    dry_run_result=dry_run_result,
                    started_at=started_at,
                    error=exc,
                )
                repo.update_sync_run_log(sync_run_id, failure_event)
                repo.commit()
                raise
        return AdsIngestionRunResult(
            workflow_name="amazon_ads_ingestion",
            mode="execute",
            status="success",
            requires_review=False,
            dry_run_result=dry_run_result,
            upsert_result=upsert_result,
            sync_run_id=upsert_result.sync_run_id,
            message="Amazon Ads ingestion completed and committed to Azure SQL.",
        )

    def _upsert_preview_rows(
        self,
        *,
        repo: AdsRepo,
        dry_run_result: AdsIngestionDryRunResult,
        source_run_id: int | None,
    ) -> list[AdsUpsertTableResult]:
        table_results: list[AdsUpsertTableResult] = []
        for report_result in dry_run_result.report_results:
            if report_result.skipped or not report_result.preview_file_path:
                continue
            table_spec = get_ads_target_table_spec(report_result.report_type_id)
            if table_spec is None:
                continue
            rows = read_jsonl(report_result.preview_file_path)
            table_results.append(
                repo.upsert_ads_rows(
                    table_spec=table_spec,
                    rows=rows,
                    source_run_id=source_run_id,
                )
            )
        return table_results


def build_final_audit_event(
    *,
    dry_run_result: AdsIngestionDryRunResult,
    upsert_result: AdsUpsertRunResult,
    started_at: str,
    status: str,
    message: str,
) -> dict[str, Any]:
    finished_at = _utc_now_iso()
    event = dict(dry_run_result.task_audit_event)
    event.update(
        {
            "workflow_name": "amazon_ads_ingestion",
            "job_name": "ingest_ads_reports",
            "task_type": "ingestion_upsert",
            "run_mode": "azure_sql_write",
            "status": status,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": _duration_ms(started_at, finished_at),
            "rows_read": dry_run_result.parsed_row_count,
            "rows_written": upsert_result.written_rows,
            "rows_skipped": upsert_result.skipped_rows,
            "rows_failed": 0,
            "message": message,
            "error_type": None,
            "error_detail": None,
        }
    )
    return event




def build_failure_audit_event(
    *,
    dry_run_result: AdsIngestionDryRunResult,
    started_at: str,
    error: Exception,
) -> dict[str, Any]:
    finished_at = _utc_now_iso()
    event = dict(dry_run_result.task_audit_event)
    event.update(
        {
            "workflow_name": "amazon_ads_ingestion",
            "job_name": "ingest_ads_reports",
            "task_type": "ingestion_upsert",
            "run_mode": "azure_sql_write",
            "status": "failed",
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": _duration_ms(started_at, finished_at),
            "rows_read": dry_run_result.parsed_row_count,
            "rows_written": 0,
            "rows_failed": dry_run_result.prepared_row_count,
            "message": "Amazon Ads ingestion failed during Azure SQL upsert.",
            "error_type": type(error).__name__,
            "error_detail": str(error),
        }
    )
    return event


def _rollback_safely(conn: Any) -> None:
    rollback = getattr(conn, "rollback", None)
    if callable(rollback):
        rollback()


def _load_schema_validation_events(output_dir: str | Path) -> list[dict[str, Any]]:
    path = Path(output_dir) / "schema_validation_events.jsonl"
    if not path.exists():
        return []
    return read_jsonl(path)


def _duration_ms(started_at: str, finished_at: str) -> int:
    start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    finish = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
    return int((finish - start).total_seconds() * 1000)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


__all__ = [
    "AdsIngestionRunResult",
    "AdsIngestionService",
    "build_failure_audit_event",
    "build_final_audit_event",
]
