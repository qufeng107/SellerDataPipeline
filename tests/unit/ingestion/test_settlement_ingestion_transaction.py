from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from seller_data_pipeline.ingestion import settlement_ingestion as module
from seller_data_pipeline.ingestion.settlement_ingestion import SettlementIngestionService


class FakeConnection:
    pass


class FakeRepo:
    def __init__(self, connection):  # noqa: ANN001
        self.connection = connection
        self.commit_count = 0
        self.rollback_count = 0
        self.updated_events = []

    def insert_sync_run_log(self, event):  # noqa: ANN001
        return 77

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1

    def update_sync_run_log(self, sync_run_id, event):  # noqa: ANN001
        self.updated_events.append((sync_run_id, event))


@contextmanager
def _fake_connection():
    yield FakeConnection()


def test_settlement_failure_rolls_back_data_but_preserves_failed_audit(monkeypatch) -> None:
    service = SettlementIngestionService(raw_reports_root="unused")
    dry_run_result = SimpleNamespace(
        requires_review=False,
        task_audit_event={
            "workflow_name": "dry",
            "job_name": "dry",
            "task_type": "dry",
            "trigger_type": "manual",
            "run_mode": "dry",
            "parent_run_id": None,
            "job_execution_id": "test",
            "marketplace_id": "ATVPDKIKX0DER",
            "source_system": "sp_api_reports",
            "status": "success",
            "started_at": "2026-08-08T00:00:00Z",
            "finished_at": "2026-08-08T00:00:01Z",
            "duration_ms": 1000,
            "date_start": None,
            "date_end": None,
            "rows_read": 2,
            "rows_written": 2,
            "rows_skipped": 0,
            "rows_failed": 0,
            "files_created": 1,
            "retry_count": 0,
            "config_snapshot_json": "{}",
            "message": "dry",
            "error_type": None,
            "error_detail": None,
        },
        prepared_row_count=2,
        schema_validation_events=(),
        preview_file_path=None,
    )
    monkeypatch.setattr(service.dry_run_service, "prepare", lambda **kwargs: dry_run_result)
    repo = FakeRepo(FakeConnection())
    monkeypatch.setattr(module, "get_connection", lambda: _fake_connection())
    monkeypatch.setattr(module, "SettlementRepo", lambda conn: repo)
    monkeypatch.setattr(
        service,
        "_upsert_preview_rows",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    with pytest.raises(RuntimeError, match="boom"):
        service.run(marketplace_id="ATVPDKIKX0DER", execute=True)

    assert repo.commit_count == 2
    assert repo.rollback_count == 1
    assert repo.updated_events[-1][0] == 77
    assert repo.updated_events[-1][1]["status"] == "failed"
