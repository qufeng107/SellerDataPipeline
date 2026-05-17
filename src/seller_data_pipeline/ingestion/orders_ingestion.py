from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from seller_data_pipeline.db.connection import get_connection
from seller_data_pipeline.db.repositories.orders_repo import OrdersRepo, OrdersUpsertRunResult
from seller_data_pipeline.ingestion.orders_ingestion_dry_run import (
    OrdersIngestionDryRunResult,
    OrdersIngestionDryRunService,
)
from seller_data_pipeline.ingestion.orders_table_mapping import read_jsonl


@dataclass(frozen=True)
class OrdersIngestionRunResult:
    workflow_name: str
    mode: str
    status: str
    requires_review: bool
    dry_run_result: OrdersIngestionDryRunResult
    upsert_result: OrdersUpsertRunResult | None
    sync_run_id: int | None
    message: str

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(asdict(self), ensure_ascii=False, default=str))


class OrdersIngestionService:
    """Guarded Orders ingestion with dry-run default and explicit Azure SQL writes."""

    def __init__(
        self,
        *,
        raw_reports_root: str | Path,
        output_root: str | Path = "runtime/ingestion/sp_api",
    ) -> None:
        self.dry_run_service = OrdersIngestionDryRunService(
            raw_reports_root=raw_reports_root,
            output_root=output_root,
        )

    def run(
        self,
        *,
        marketplace_id: str,
        raw_file_path: str | Path | None = None,
        execute: bool = False,
        fail_on_review: bool = True,
    ) -> OrdersIngestionRunResult:
        dry_run_result = self.dry_run_service.prepare(
            marketplace_id=marketplace_id,
            raw_file_path=raw_file_path,
            fail_on_review=fail_on_review,
        )
        if dry_run_result.requires_review:
            return OrdersIngestionRunResult(
                workflow_name="sp_api_orders_ingestion",
                mode="dry_run" if not execute else "execute_blocked",
                status="requires_review",
                requires_review=True,
                dry_run_result=dry_run_result,
                upsert_result=None,
                sync_run_id=None,
                message=(
                    "Orders ingestion requires schema/privacy review; Azure SQL write was blocked."
                ),
            )
        if not execute:
            return OrdersIngestionRunResult(
                workflow_name="sp_api_orders_ingestion",
                mode="dry_run",
                status="dry_run_success",
                requires_review=False,
                dry_run_result=dry_run_result,
                upsert_result=None,
                sync_run_id=None,
                message="Orders ingestion dry-run completed; no Azure SQL writes were performed.",
            )

        started_at = _utc_now_iso()
        initial_event = build_running_audit_event(
            dry_run_result=dry_run_result,
            started_at=started_at,
        )
        with get_connection() as conn:
            repo = OrdersRepo(conn)
            sync_run_id = repo.insert_sync_run_log(initial_event)
            try:
                upsert_result = self._upsert_preview_rows(
                    repo=repo,
                    dry_run_result=dry_run_result,
                    source_run_id=sync_run_id,
                )
                repo.insert_schema_validation_events(
                    [dry_run_result.report_result.schema_validation_event]
                    if dry_run_result.report_result.schema_validation_event
                    else [],
                    source_run_id=sync_run_id,
                )
                finished_event = build_finished_audit_event(
                    dry_run_result=dry_run_result,
                    upsert_result=upsert_result,
                    started_at=started_at,
                    status="success",
                    message="SP-API Orders ingestion completed successfully.",
                )
                repo.update_sync_run_log(sync_run_id, finished_event)
                repo.commit()
            except Exception as exc:
                failed_event = build_finished_audit_event(
                    dry_run_result=dry_run_result,
                    upsert_result=None,
                    started_at=started_at,
                    status="failed",
                    message="SP-API Orders ingestion failed and was rolled back.",
                    error=exc,
                )
                repo.update_sync_run_log(sync_run_id, failed_event)
                repo.commit()
                raise

        return OrdersIngestionRunResult(
            workflow_name="sp_api_orders_ingestion",
            mode="execute",
            status="success",
            requires_review=False,
            dry_run_result=dry_run_result,
            upsert_result=OrdersUpsertRunResult(
                table_result=upsert_result.table_result,
                sync_run_id=sync_run_id,
            ),
            sync_run_id=sync_run_id,
            message="SP-API Orders ingestion completed and committed to Azure SQL.",
        )

    def _upsert_preview_rows(
        self,
        *,
        repo: OrdersRepo,
        dry_run_result: OrdersIngestionDryRunResult,
        source_run_id: int,
    ) -> OrdersUpsertRunResult:
        preview_path = dry_run_result.report_result.preview_file_path
        rows = read_jsonl(preview_path) if preview_path else []
        table_result = repo.upsert_order_item_rows(
            rows=rows,
            source_run_id=source_run_id,
        )
        return OrdersUpsertRunResult(table_result=table_result, sync_run_id=source_run_id)


def build_running_audit_event(
    *,
    dry_run_result: OrdersIngestionDryRunResult,
    started_at: str,
) -> dict[str, Any]:
    return {
        **dry_run_result.task_audit_event,
        "workflow_name": "sp_api_orders_ingestion",
        "job_name": "ingest_orders_report",
        "task_type": "ingestion_upsert",
        "run_mode": "azure_sql_write",
        "status": "running",
        "started_at": started_at,
        "finished_at": None,
        "duration_ms": None,
        "rows_read": dry_run_result.prepared_row_count,
        "rows_written": 0,
        "rows_skipped": 0,
        "rows_failed": 0,
        "message": "SP-API Orders ingestion is running.",
        "error_type": None,
        "error_detail": None,
    }


def build_finished_audit_event(
    *,
    dry_run_result: OrdersIngestionDryRunResult,
    upsert_result: OrdersUpsertRunResult | None,
    started_at: str,
    status: str,
    message: str,
    error: Exception | None = None,
) -> dict[str, Any]:
    finished_at = _utc_now_iso()
    attempted = upsert_result.attempted_rows if upsert_result else dry_run_result.prepared_row_count
    written = upsert_result.written_rows if upsert_result else 0
    skipped = upsert_result.skipped_rows if upsert_result else 0
    failed = 0 if status == "success" else attempted
    return {
        **dry_run_result.task_audit_event,
        "workflow_name": "sp_api_orders_ingestion",
        "job_name": "ingest_orders_report",
        "task_type": "ingestion_upsert",
        "run_mode": "azure_sql_write",
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": _duration_ms(started_at, finished_at),
        "rows_read": attempted,
        "rows_written": written,
        "rows_skipped": skipped,
        "rows_failed": failed,
        "message": message,
        "error_type": type(error).__name__ if error else None,
        "error_detail": str(error)[:4000] if error else None,
    }


def _duration_ms(started_at: str, finished_at: str) -> int:
    start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    finish = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
    return int((finish - start).total_seconds() * 1000)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


__all__ = [
    "OrdersIngestionRunResult",
    "OrdersIngestionService",
    "build_finished_audit_event",
    "build_running_audit_event",
]
