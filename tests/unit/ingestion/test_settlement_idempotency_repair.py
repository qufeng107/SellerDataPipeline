from __future__ import annotations

from contextlib import contextmanager

from seller_data_pipeline.ingestion import settlement_idempotency_repair as module
from seller_data_pipeline.ingestion.settlement_idempotency_repair import (
    SettlementIdempotencyRepairService,
    build_repair_plans,
)
from seller_data_pipeline.ingestion.settlement_table_mapping import (
    SETTLEMENT_TARGET_TABLE_SPEC,
    compute_business_key_hash,
)


def _canonical_hash(
    *,
    marketplace_id: str = "ATVPDKIKX0DER",
    source_report_id: str = "112639020588",
    source_row_index: int = 7,
    source_row_hash: str = "row-hash",
) -> str:
    return compute_business_key_hash(
        target_table=SETTLEMENT_TARGET_TABLE_SPEC.target_table,
        business_key_fields=SETTLEMENT_TARGET_TABLE_SPEC.business_key_fields,
        row={
            "marketplace_id": marketplace_id,
            "source_report_id": source_report_id,
            "source_row_index": source_row_index,
            "source_row_hash": source_row_hash,
        },
    )


def _row(
    row_id: int,
    business_key_hash: str | None,
    *,
    marketplace_id: str = "ATVPDKIKX0DER",
    source_report_id: str = "112639020588",
    source_row_index: int = 7,
    source_row_hash: str = "row-hash",
) -> dict[str, object]:
    return {
        "id": row_id,
        "marketplace_id": marketplace_id,
        "source_report_id": source_report_id,
        "source_row_index": source_row_index,
        "source_row_hash": source_row_hash,
        "business_key_hash": business_key_hash,
        "source_raw_file_path": f"report-{row_id}.txt",
        "source_run_id": row_id,
    }


def test_repair_plan_prefers_existing_canonical_row() -> None:
    canonical_hash = _canonical_hash()
    plans = build_repair_plans(
        [
            _row(10, "legacy-hash"),
            _row(20, canonical_hash),
        ]
    )

    assert len(plans) == 1
    plan = plans[0]
    assert plan.status == "repairable"
    assert plan.keep_row_id == 20
    assert plan.keep_requires_hash_update is False
    assert plan.delete_row_ids == (10,)
    assert plan.canonical_business_key_hash == canonical_hash


def test_repair_plan_uses_newest_row_when_canonical_hash_is_not_owned() -> None:
    plans = build_repair_plans(
        [
            _row(10, "legacy-a"),
            _row(20, "legacy-b"),
        ]
    )

    plan = plans[0]
    assert plan.status == "repairable"
    assert plan.keep_row_id == 20
    assert plan.keep_requires_hash_update is True
    assert plan.delete_row_ids == (10,)


def test_repair_plan_blocks_cross_identity_business_key_owner() -> None:
    canonical_hash = _canonical_hash()
    plans = build_repair_plans(
        [
            _row(10, "legacy-a"),
            _row(20, "legacy-b"),
            _row(
                999,
                canonical_hash,
                source_report_id="other-report",
                source_row_index=99,
                source_row_hash="other-row-hash",
            ),
        ]
    )

    plan = next(plan for plan in plans if plan.identity.source_report_id == "112639020588")
    assert plan.status == "conflict"
    assert plan.requires_review is True
    assert plan.keep_row_id is None
    assert plan.keep_requires_hash_update is False
    assert plan.delete_row_ids == ()


def test_repair_planning_scales_in_memory_without_per_group_repository_queries() -> None:
    rows: list[dict[str, object]] = []
    for index in range(4000):
        report_id = f"report-{index}"
        row_hash = f"row-hash-{index}"
        canonical_hash = _canonical_hash(
            source_report_id=report_id,
            source_row_index=index,
            source_row_hash=row_hash,
        )
        rows.extend(
            [
                _row(
                    index * 2 + 1,
                    f"legacy-{index}",
                    source_report_id=report_id,
                    source_row_index=index,
                    source_row_hash=row_hash,
                ),
                _row(
                    index * 2 + 2,
                    canonical_hash,
                    source_report_id=report_id,
                    source_row_index=index,
                    source_row_hash=row_hash,
                ),
            ]
        )

    plans = build_repair_plans(rows)

    assert len(plans) == 4000
    assert all(plan.status == "repairable" for plan in plans)
    assert sum(plan.rows_to_delete for plan in plans) == 4000
    assert sum(plan.keep_requires_hash_update for plan in plans) == 0


class FakeConnection:
    pass


class FakeRepo:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.scan_calls = 0
        self.delete_calls: list[list[int]] = []
        self.rekey_calls: list[list[tuple[int, str]]] = []
        self.commit_count = 0
        self.rollback_count = 0

    def fetch_idempotency_repair_rows(self, *, marketplace_id=None):  # noqa: ANN001
        self.scan_calls += 1
        return list(self.rows)

    def delete_transaction_rows_by_ids(self, row_ids):  # noqa: ANN001
        self.delete_calls.append(list(row_ids))
        return len(row_ids)

    def update_transaction_business_key_hashes(self, rows):  # noqa: ANN001
        self.rekey_calls.append(list(rows))
        return len(rows)

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1


@contextmanager
def _fake_connection(*, autocommit=False):  # noqa: ANN001
    yield FakeConnection()


def test_service_uses_single_scan_and_bulk_execute(monkeypatch) -> None:
    rows = [_row(1, "legacy-a"), _row(2, "legacy-b")]
    repo = FakeRepo(rows)
    monkeypatch.setattr(module, "get_connection", _fake_connection)
    monkeypatch.setattr(module, "SettlementRepo", lambda conn: repo)

    result = SettlementIdempotencyRepairService().run(
        marketplace_id="ATVPDKIKX0DER",
        execute=True,
    )

    assert result.status == "success"
    assert result.scanned_row_count == 2
    assert result.duplicate_group_count == 1
    assert result.rows_deleted == 1
    assert result.rows_rekeyed == 1
    assert repo.scan_calls == 1
    assert repo.delete_calls == [[1]]
    assert len(repo.rekey_calls) == 1
    assert repo.rekey_calls[0][0][0] == 2
    assert repo.commit_count == 1
    assert repo.rollback_count == 0
