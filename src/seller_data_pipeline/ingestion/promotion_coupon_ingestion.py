from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from seller_data_pipeline.db.connection import get_connection
from seller_data_pipeline.db.repositories.promotion_coupon_repo import (
    PromotionCouponRepo,
    PromotionCouponUpsertRunResult,
    PromotionCouponUpsertTableResult,
)
from seller_data_pipeline.ingestion.promotion_coupon_ingestion_dry_run import (
    PromotionCouponIngestionDryRunResult,
    PromotionCouponIngestionDryRunService,
)
from seller_data_pipeline.ingestion.promotion_coupon_table_mapping import (
    get_promotion_coupon_target_table_spec,
    read_jsonl,
)


@dataclass(frozen=True)
class PromotionCouponIngestionRunResult:
    workflow_name: str
    mode: str
    status: str
    requires_review: bool
    dry_run_result: PromotionCouponIngestionDryRunResult
    upsert_result: PromotionCouponUpsertRunResult | None
    sync_run_id: int | None
    message: str

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(asdict(self), ensure_ascii=False, default=str))


class PromotionCouponIngestionService:
    """Guarded Promotion/Coupon ingestion with dry-run default and explicit Azure SQL writes."""

    def __init__(
        self,
        *,
        raw_reports_root: str | Path,
        output_root: str | Path = "runtime/ingestion/sp_api",
    ) -> None:
        self.dry_run_service = PromotionCouponIngestionDryRunService(
            raw_reports_root=raw_reports_root,
            output_root=output_root,
        )

    def run(
        self,
        *,
        marketplace_id: str,
        promotion_raw_file_path: str | Path | None = None,
        coupon_raw_file_path: str | Path | None = None,
        execute: bool = False,
        fail_on_review: bool = True,
    ) -> PromotionCouponIngestionRunResult:
        dry_run_result = self.dry_run_service.prepare(
            marketplace_id=marketplace_id,
            promotion_raw_file_path=promotion_raw_file_path,
            coupon_raw_file_path=coupon_raw_file_path,
            fail_on_review=fail_on_review,
        )
        if dry_run_result.requires_review:
            return PromotionCouponIngestionRunResult(
                workflow_name="sp_api_promotion_coupon_ingestion",
                mode="execute" if execute else "dry_run",
                status="blocked_requires_review",
                requires_review=True,
                dry_run_result=dry_run_result,
                upsert_result=None,
                sync_run_id=None,
                message="Schema/table validation requires manual review; database write skipped.",
            )
        if not execute:
            return PromotionCouponIngestionRunResult(
                workflow_name="sp_api_promotion_coupon_ingestion",
                mode="dry_run",
                status="dry_run_success",
                requires_review=False,
                dry_run_result=dry_run_result,
                upsert_result=None,
                sync_run_id=None,
                message="Promotion/Coupon ingestion dry-run completed; no Azure SQL writes were performed.",
            )

        started_at = _utc_now_iso()
        initial_event = build_running_audit_event(
            dry_run_result=dry_run_result,
            started_at=started_at,
        )
        with get_connection(autocommit=False) as conn:
            repo = PromotionCouponRepo(conn)
            sync_run_id = repo.insert_sync_run_log(initial_event)
            try:
                upsert_result = self._upsert_preview_rows(
                    repo=repo,
                    dry_run_result=dry_run_result,
                    source_run_id=sync_run_id,
                )
                schema_events = _load_schema_validation_events(dry_run_result.output_dir)
                repo.insert_schema_validation_events(schema_events, source_run_id=sync_run_id)
                finished_event = build_finished_audit_event(
                    dry_run_result=dry_run_result,
                    upsert_result=upsert_result,
                    started_at=started_at,
                    status="success",
                    message="SP-API Promotion/Coupon ingestion completed successfully.",
                )
                repo.update_sync_run_log(sync_run_id, finished_event)
                repo.commit()
            except Exception as exc:
                _rollback_safely(conn)
                failed_event = build_finished_audit_event(
                    dry_run_result=dry_run_result,
                    upsert_result=None,
                    started_at=started_at,
                    status="failed",
                    message="SP-API Promotion/Coupon ingestion failed and was rolled back.",
                    error=exc,
                )
                repo.update_sync_run_log(sync_run_id, failed_event)
                repo.commit()
                raise
        return PromotionCouponIngestionRunResult(
            workflow_name="sp_api_promotion_coupon_ingestion",
            mode="execute",
            status="success",
            requires_review=False,
            dry_run_result=dry_run_result,
            upsert_result=PromotionCouponUpsertRunResult(
                table_results=upsert_result.table_results,
                sync_run_id=sync_run_id,
            ),
            sync_run_id=sync_run_id,
            message="SP-API Promotion/Coupon ingestion completed and committed to Azure SQL.",
        )

    def _upsert_preview_rows(
        self,
        *,
        repo: PromotionCouponRepo,
        dry_run_result: PromotionCouponIngestionDryRunResult,
        source_run_id: int,
    ) -> PromotionCouponUpsertRunResult:
        table_results: list[PromotionCouponUpsertTableResult] = []
        for report_result in dry_run_result.report_results:
            if report_result.skipped:
                continue
            for table_name, preview_path in report_result.preview_file_paths.items():
                table_spec = get_promotion_coupon_target_table_spec(table_name)
                if table_spec is None:
                    continue
                rows = read_jsonl(preview_path)
                table_results.append(
                    repo.upsert_rows(
                        table_spec=table_spec,
                        rows=rows,
                        source_run_id=source_run_id,
                    )
                )
        return PromotionCouponUpsertRunResult(
            table_results=tuple(table_results),
            sync_run_id=source_run_id,
        )


def build_running_audit_event(
    *,
    dry_run_result: PromotionCouponIngestionDryRunResult,
    started_at: str,
) -> dict[str, Any]:
    return {
        **dry_run_result.task_audit_event,
        "workflow_name": "sp_api_promotion_coupon_ingestion",
        "job_name": "ingest_promotion_coupon_reports",
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
        "message": "SP-API Promotion/Coupon ingestion is running.",
        "error_type": None,
        "error_detail": None,
    }


def build_finished_audit_event(
    *,
    dry_run_result: PromotionCouponIngestionDryRunResult,
    upsert_result: PromotionCouponUpsertRunResult | None,
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
        "workflow_name": "sp_api_promotion_coupon_ingestion",
        "job_name": "ingest_promotion_coupon_reports",
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


def _load_schema_validation_events(output_dir: str | Path) -> list[dict[str, Any]]:
    path = Path(output_dir) / "schema_validation_events.jsonl"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def _rollback_safely(conn: Any) -> None:
    try:
        conn.rollback()
    except Exception:
        return


def _duration_ms(started_at: str, finished_at: str) -> int:
    start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    finish = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
    return int((finish - start).total_seconds() * 1000)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


__all__ = [
    "PromotionCouponIngestionRunResult",
    "PromotionCouponIngestionService",
    "build_finished_audit_event",
    "build_running_audit_event",
]
