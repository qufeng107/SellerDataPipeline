from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from seller_data_pipeline.services.automation_schedule_service import AutomationCommand
from seller_data_pipeline.services.pipeline_job_audit_service import (
    AutomationAuditContext,
    AutomationAuditWindow,
    PipelineJobAuditService,
    build_config_snapshot,
    command_line_hash,
)


def test_pipeline_job_audit_service_redacts_command_args_and_records_command() -> None:
    repo = _FakeAuditRepo()
    service = PipelineJobAuditService(repo=repo)  # type: ignore[arg-type]
    started_at = datetime(2026, 5, 29, tzinfo=UTC)
    service.start_run(
        AutomationAuditContext(
            workflow="weekly",
            phase="submit",
            execution_mode="execute",
            configured_trigger_type="Schedule",
            run_trigger_type="unknown",
            run_trigger_source="default:unknown",
            marketplace_id="ATVPDKIKX0DER",
            profile_id="3917953989967300",
            artifact_scope="weekly:scope",
            window=AutomationAuditWindow(
                period_key="2026-05-16_2026-05-22",
                stats_start=None,
                stats_end=None,
                request_start=None,
                request_end=None,
            ),
            command_line_hash="a" * 64,
            config_snapshot_json="{}",
            started_at=started_at,
        )
    )

    handle = service.command_started(
        1,
        AutomationCommand(
            label="Sensitive command",
            argv=("scripts/example.py", "--refresh-token", "secret-token-value"),
            writes_external_or_database=True,
        ),
        started_at,
    )
    service.command_finished(handle, 0, datetime(2026, 5, 29, 0, 0, 1, tzinfo=UTC))

    assert repo.job_runs[0].workflow == "weekly"
    command = repo.commands[0]
    assert command.command_label == "Sensitive command"
    assert "secret-token-value" not in (command.redacted_args_json or "")
    assert "***REDACTED***" in (command.redacted_args_json or "")
    assert repo.updated_commands[0]["status"] == "succeeded"


def test_pipeline_job_audit_service_extracts_table_write_summaries(tmp_path: Path) -> None:
    repo = _FakeAuditRepo()
    service = PipelineJobAuditService(repo=repo)  # type: ignore[arg-type]
    service.job_run_id = 7
    output_dir = tmp_path / "runtime" / "ingestion" / "sp_api"
    output_dir.mkdir(parents=True)
    summary_path = output_dir / "orders_result.json"
    summary_path.write_text(
        json.dumps(
            {
                "workflow_name": "sp_api_orders_ingestion",
                "status": "success",
                "requires_review": False,
                "dry_run_result": {
                    "report_result": {
                        "raw_file_path": "reports/raw/amazon/orders.txt",
                    }
                },
                "upsert_result": {
                    "table_result": {
                        "table_name": "amazon_order_item",
                        "report_type": "GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL",
                        "attempted_rows": 32,
                        "inserted_rows": 30,
                        "updated_rows": 2,
                        "skipped_rows": 0,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    from seller_data_pipeline.services.pipeline_artifact_service import (
        ArtifactSaveResult,
        SavedArtifact,
    )

    count = service.insert_table_write_summaries_from_saved_artifacts(
        save_result=ArtifactSaveResult(
            artifact_scope="weekly:scope",
            dry_run=False,
            scanned_count=1,
            saved_artifacts=(
                SavedArtifact(
                    artifact_id=1,
                    artifact_type="ingestion_output",
                    relative_path=str(summary_path.relative_to(tmp_path)).replace("\\", "/"),
                    content_size_bytes=10,
                    compressed_size_bytes=8,
                    content_sha256="a" * 64,
                ),
            ),
            skipped_paths=(),
        ),
        root=tmp_path,
    )

    assert count == 1
    item = repo.table_write_summaries[0]
    assert item.target_table == "amazon_order_item"
    assert item.rows_read == 32
    assert item.rows_inserted == 30
    assert item.rows_updated == 2
    assert item.source_raw_file_path == "reports/raw/amazon/orders.txt"


def test_build_config_snapshot_omits_recipient_values() -> None:
    snapshot = build_config_snapshot(
        workflow="weekly",
        phase="report_delivery",
        reference_date=datetime(2026, 5, 29, tzinfo=UTC).date(),
        week_start=None,
        month=None,
        send_email=True,
        force_resend=False,
        continue_on_error=False,
        skip_artifact_store=False,
        email_to=("feng@cuidena.cn", "ops@example.com"),
    )

    assert "email_to_count" in snapshot
    assert "feng@cuidena.cn" not in snapshot


def test_command_line_hash_is_stable() -> None:
    assert command_line_hash(["a", "b"]) == command_line_hash(["a", "b"])
    assert command_line_hash(["a", "b"]) != command_line_hash(["a", "c"])


class _FakeAuditRepo:
    def __init__(self) -> None:
        self.job_runs: list[Any] = []
        self.commands: list[Any] = []
        self.updated_commands: list[dict[str, Any]] = []
        self.table_write_summaries: list[Any] = []

    def insert_job_run(self, item: Any) -> int:
        self.job_runs.append(item)
        return 7

    def insert_command_run(self, item: Any) -> int:
        self.commands.append(item)
        return 11

    def update_command_run(self, **kwargs: Any) -> None:
        self.updated_commands.append(kwargs)

    def insert_table_write_summary(self, item: Any) -> None:
        self.table_write_summaries.append(item)
