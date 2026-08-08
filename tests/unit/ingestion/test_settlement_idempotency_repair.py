from __future__ import annotations

from seller_data_pipeline.ingestion.settlement_idempotency_repair import (
    SettlementDuplicateIdentity,
    SettlementIdempotencyRepairService,
)
from seller_data_pipeline.ingestion.settlement_table_mapping import (
    SETTLEMENT_TARGET_TABLE_SPEC,
    compute_business_key_hash,
)


class FakeRepo:
    def __init__(self, *, rows, owner=None):
        self.rows = rows
        self.owner = owner

    def fetch_source_identity_rows(self, **kwargs):  # noqa: ANN003
        return list(self.rows)

    def fetch_business_key_owner(self, business_key_hash: str):
        return self.owner


def _identity() -> SettlementDuplicateIdentity:
    return SettlementDuplicateIdentity(
        marketplace_id="ATVPDKIKX0DER",
        source_report_id="112639020588",
        source_row_index=7,
        source_row_hash="row-hash",
        duplicate_count=2,
    )


def _canonical_hash(identity: SettlementDuplicateIdentity) -> str:
    return compute_business_key_hash(
        target_table=SETTLEMENT_TARGET_TABLE_SPEC.target_table,
        business_key_fields=SETTLEMENT_TARGET_TABLE_SPEC.business_key_fields,
        row=identity.as_key_row(),
    )


def test_repair_plan_prefers_existing_canonical_row() -> None:
    identity = _identity()
    canonical_hash = _canonical_hash(identity)
    repo = FakeRepo(
        rows=[
            {"id": 10, "business_key_hash": "legacy-hash"},
            {"id": 20, "business_key_hash": canonical_hash},
        ],
        owner={"id": 20},
    )

    plan = SettlementIdempotencyRepairService()._build_plan(repo=repo, identity=identity)

    assert plan.status == "repairable"
    assert plan.keep_row_id == 20
    assert plan.delete_row_ids == (10,)
    assert plan.canonical_business_key_hash == canonical_hash


def test_repair_plan_uses_newest_row_when_canonical_hash_is_not_owned() -> None:
    identity = _identity()
    repo = FakeRepo(
        rows=[
            {"id": 10, "business_key_hash": "legacy-a"},
            {"id": 20, "business_key_hash": "legacy-b"},
        ],
        owner=None,
    )

    plan = SettlementIdempotencyRepairService()._build_plan(repo=repo, identity=identity)

    assert plan.status == "repairable"
    assert plan.keep_row_id == 20
    assert plan.delete_row_ids == (10,)


def test_repair_plan_blocks_cross_identity_business_key_owner() -> None:
    identity = _identity()
    repo = FakeRepo(
        rows=[
            {"id": 10, "business_key_hash": "legacy-a"},
            {"id": 20, "business_key_hash": "legacy-b"},
        ],
        owner={"id": 999},
    )

    plan = SettlementIdempotencyRepairService()._build_plan(repo=repo, identity=identity)

    assert plan.status == "conflict"
    assert plan.requires_review is True
    assert plan.keep_row_id is None
    assert plan.delete_row_ids == ()
