from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from seller_data_pipeline.db.connection import get_connection
from seller_data_pipeline.db.repositories.inventory_repo import (
    InventoryRepo,
    InventoryUpsertRunResult,
)
from seller_data_pipeline.ingestion.inventory_ingestion_dry_run import (
    InventoryIngestionDryRunResult,
    InventoryIngestionDryRunService,
)
from seller_data_pipeline.ingestion.inventory_table_mapping import read_jsonl


@dataclass(frozen=True)
class InventoryIngestionRunResult:
    workflow_name: str
    mode: str
    status: str
    requires_review: bool
    dry_run_result: InventoryIngestionDryRunResult
    upsert_result: InventoryUpsertRunResult | None
    sync_run_id: int | None
    message: str

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(asdict(self), ensure_ascii=False, default=str))


class InventoryIngestionService:
    """Guarded Inventory ingestion workflow with dry-run default and explicit Azure SQL writes."""

    def __init__(
        self,
        *,
        raw_reports_root: str | Path,
        output_root: str | Path = "runtime/ingestion/sp_api",
    ) -> None:
        self.dry_run_service = InventoryIngestionDryRunService(
            raw_reports_root=raw_reports_root,
            output_root=output_root,
        )

    def run(
        self,
        *,
        marketplace_id: str,
        raw_file_path: str | Path | None = None,
        snapshot_date: date | None = None,
        currency: str | None = "USD",
        execute: bool = False,
        fail_on_review: bool = True,
    ) -> InventoryIngestionRunResult:
        dry_run_result = self.dry_run_service.prepare(
            marketplace_id=marketplace_id,
            raw_file_path=raw_file_path,
            snapshot_date=snapshot_date,
            currency=currency,
            fail_on_review=fail_on_review,
        )
        if dry_run_result.requires_review:
            return InventoryIngestionRunResult(
                workflow_name="sp_api_inventory_ingestion",
                mode="dry_run" if not execute else "execute_blocked",
                status="requires_review",
                requires_review=True,
                dry_run_result=dry_run_result,
                upsert_result=None,
                sync_run_id=None,
                message="Inventory ingestion requires schema review; Azure SQL write was blocked.",
            )
        if not execute:
            return InventoryIngestionRunResult(
                workflow_name="sp_api_inventory_ingestion",
                mode="dry_run",
                status="dry_run_success",
                requires_review=False,
                dry_run_result=dry_run_result,
                upsert_result=None,
                sync_run_id=None,
                message="Inventory ingestion dry-run completed; no Azure SQL writes were performed.",
            )

        started_at = _utc_now_iso()
        initial_event = build_running_audit_event(
            dry_run_result=dry_run_result,
            started_at=started_at,
        )
        with get_connection() as conn:
            repo = InventoryRepo(conn)
            sync_run_id = repo.insert_sync_run_log(initial_event)
            try:
                table_result = self._upsert_preview_rows(
                    repo=repo,
                    dry_run_result=dry_run_result,
                    source_run_id=sync_run_id,
                )
                upsert_result = InventoryUpsertRunResult(
                    table_result=table_result,
                    sync_run_id=sync_run_id,
                )
                repo.insert_schema_validation_events(
                    [dry_run_result.report_result.schema_validation_event]
                    if dry_run_result.report_result.schema_validation_event is not None
                    else [],
                    source_run_id=sync_run_id,
                )
                final_event = build_final_audit_event(
                    dry_run_result=dry_run_result,
                    upsert_result=upsert_result,
                    started_at=started_at,
                    status="success",
                    message="SP-API Inventory ingestion committed to Azure SQL.",
                )
                repo.update_sync_run_log(sync_run_id, final_event)
                repo.commit()
            except Exception as exc:
                failure_event = build_failure_audit_event(
                    dry_run_result=dry_run_result,
                    started_at=started_at,
                    error=exc,
                )
                repo.update_sync_run_log(sync_run_id, failure_event)
                repo.commit()
                raise
        return InventoryIngestionRunResult(
            workflow_name="sp_api_inventory_ingestion",
            mode="execute",
            status="success",
            requires_review=False,
            dry_run_result=dry_run_result,
            upsert_result=upsert_result,
            sync_run_id=upsert_result.sync_run_id,
            message="SP-API Inventory ingestion completed and committed to Azure SQL.",
        )

    def _upsert_preview_rows(
        self,
        *,
        repo: InventoryRepo,
        dry_run_result: InventoryIngestionDryRunResult,
        source_run_id: int | None,
    ):
        preview_path = dry_run_result.report_result.preview_file_path
        if not preview_path:
            return repo.upsert_inventory_rows(rows=[], source_run_id=source_run_id)
        rows = read_jsonl(preview_path)
        return repo.upsert_inventory_rows(rows=rows, source_run_id=source_run_id)


def build_running_audit_event(
    *,
    dry_run_result: InventoryIngestionDryRunResult,
    started_at: str,
) -> dict[str, Any]:
    event = dict(dry_run_result.task_audit_event)
    event.update(
        {
            "workflow_name": "sp_api_inventory_ingestion",
            "job_name": "ingest_inventory_snapshot",
            "task_type": "ingestion_upsert",
            "run_mode": "azure_sql_write",
            "status": "running",
            "started_at": started_at,
            "finished_at": None,
            "duration_ms": None,
            "rows_written": 0,
            "rows_failed": 0,
            "message": "SP-API Inventory ingestion is writing to Azure SQL.",
            "error_type": None,
            "error_detail": None,
        }
    )
    return event


def build_final_audit_event(
    *,
    dry_run_result: InventoryIngestionDryRunResult,
    upsert_result: InventoryUpsertRunResult,
    started_at: str,
    status: str,
    message: str,
) -> dict[str, Any]:
    finished_at = _utc_now_iso()
    event = dict(dry_run_result.task_audit_event)
    event.update(
        {
            "workflow_name": "sp_api_inventory_ingestion",
            "job_name": "ingest_inventory_snapshot",
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
    dry_run_result: InventoryIngestionDryRunResult,
    started_at: str,
    error: Exception,
) -> dict[str, Any]:
    finished_at = _utc_now_iso()
    event = dict(dry_run_result.task_audit_event)
    event.update(
        {
            "workflow_name": "sp_api_inventory_ingestion",
            "job_name": "ingest_inventory_snapshot",
            "task_type": "ingestion_upsert",
            "run_mode": "azure_sql_write",
            "status": "failed",
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": _duration_ms(started_at, finished_at),
            "rows_read": dry_run_result.parsed_row_count,
            "rows_written": 0,
            "rows_failed": dry_run_result.prepared_row_count,
            "message": "SP-API Inventory ingestion failed during Azure SQL upsert.",
            "error_type": type(error).__name__,
            "error_detail": str(error),
        }
    )
    return event


def _duration_ms(started_at: str, finished_at: str) -> int:
    start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    finish = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
    return int((finish - start).total_seconds() * 1000)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


__all__ = [
    "InventoryIngestionRunResult",
    "InventoryIngestionService",
    "build_failure_audit_event",
    "build_final_audit_event",
    "build_running_audit_event",
]
