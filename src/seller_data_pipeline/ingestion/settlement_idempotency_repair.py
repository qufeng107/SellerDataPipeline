from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from seller_data_pipeline.db.connection import get_connection
from seller_data_pipeline.db.repositories.settlement_repo import SettlementRepo
from seller_data_pipeline.ingestion.settlement_table_mapping import (
    SETTLEMENT_TARGET_TABLE_SPEC,
    compute_business_key_hash,
)


@dataclass(frozen=True)
class SettlementDuplicateIdentity:
    marketplace_id: str
    source_report_id: str
    source_row_index: int
    source_row_hash: str
    duplicate_count: int

    def as_key_row(self) -> dict[str, Any]:
        return {
            "marketplace_id": self.marketplace_id,
            "source_report_id": self.source_report_id,
            "source_row_index": self.source_row_index,
            "source_row_hash": self.source_row_hash,
        }


@dataclass(frozen=True)
class SettlementDuplicateRepairPlan:
    identity: SettlementDuplicateIdentity
    canonical_business_key_hash: str
    keep_row_id: int | None
    delete_row_ids: tuple[int, ...]
    status: str
    message: str

    @property
    def requires_review(self) -> bool:
        return self.status == "conflict"

    @property
    def rows_to_delete(self) -> int:
        return len(self.delete_row_ids)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SettlementIdempotencyRepairResult:
    mode: str
    status: str
    marketplace_id: str | None
    duplicate_group_count: int
    repairable_group_count: int
    conflict_group_count: int
    rows_to_delete: int
    rows_deleted: int
    plans: tuple[SettlementDuplicateRepairPlan, ...]

    @property
    def requires_review(self) -> bool:
        return self.conflict_group_count > 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SettlementIdempotencyRepairService:
    """Audit and repair exact duplicate Settlement source rows.

    This maintenance path is intentionally narrower than normal ingestion. It only
    touches rows whose immutable source identity is exactly equal:
    marketplace_id + source_report_id + source_row_index + source_row_hash.
    """

    def run(
        self,
        *,
        marketplace_id: str | None = None,
        execute: bool = False,
    ) -> SettlementIdempotencyRepairResult:
        with get_connection(autocommit=False) as conn:
            repo = SettlementRepo(conn)
            identities = [
                _identity_from_row(row)
                for row in repo.fetch_duplicate_source_identities(
                    marketplace_id=marketplace_id
                )
            ]
            plans = tuple(self._build_plan(repo=repo, identity=identity) for identity in identities)
            conflicts = tuple(plan for plan in plans if plan.requires_review)
            repairable = tuple(plan for plan in plans if not plan.requires_review)

            if conflicts:
                repo.rollback()
                return SettlementIdempotencyRepairResult(
                    mode="execute_blocked" if execute else "dry_run",
                    status="requires_review",
                    marketplace_id=marketplace_id,
                    duplicate_group_count=len(plans),
                    repairable_group_count=len(repairable),
                    conflict_group_count=len(conflicts),
                    rows_to_delete=sum(plan.rows_to_delete for plan in repairable),
                    rows_deleted=0,
                    plans=plans,
                )

            rows_deleted = 0
            if execute:
                try:
                    for plan in repairable:
                        if plan.delete_row_ids:
                            rows_deleted += repo.delete_transaction_rows_by_ids(
                                list(plan.delete_row_ids)
                            )
                        if plan.keep_row_id is not None:
                            repo.update_transaction_business_key_hash(
                                row_id=plan.keep_row_id,
                                business_key_hash=plan.canonical_business_key_hash,
                            )
                    repo.commit()
                except Exception:
                    repo.rollback()
                    raise
            else:
                repo.rollback()

        return SettlementIdempotencyRepairResult(
            mode="execute" if execute else "dry_run",
            status="success",
            marketplace_id=marketplace_id,
            duplicate_group_count=len(plans),
            repairable_group_count=len(repairable),
            conflict_group_count=0,
            rows_to_delete=sum(plan.rows_to_delete for plan in repairable),
            rows_deleted=rows_deleted,
            plans=plans,
        )

    def _build_plan(
        self,
        *,
        repo: SettlementRepo,
        identity: SettlementDuplicateIdentity,
    ) -> SettlementDuplicateRepairPlan:
        rows = repo.fetch_source_identity_rows(
            marketplace_id=identity.marketplace_id,
            source_report_id=identity.source_report_id,
            source_row_index=identity.source_row_index,
            source_row_hash=identity.source_row_hash,
        )
        canonical_hash = compute_business_key_hash(
            target_table=SETTLEMENT_TARGET_TABLE_SPEC.target_table,
            business_key_fields=SETTLEMENT_TARGET_TABLE_SPEC.business_key_fields,
            row=identity.as_key_row(),
        )
        group_ids = {int(row["id"]) for row in rows}
        owner = repo.fetch_business_key_owner(canonical_hash)
        if owner is not None and int(owner["id"]) not in group_ids:
            return SettlementDuplicateRepairPlan(
                identity=identity,
                canonical_business_key_hash=canonical_hash,
                keep_row_id=None,
                delete_row_ids=(),
                status="conflict",
                message=(
                    "Canonical business key is owned by a different source identity; "
                    "automatic repair was blocked."
                ),
            )

        if not rows:
            return SettlementDuplicateRepairPlan(
                identity=identity,
                canonical_business_key_hash=canonical_hash,
                keep_row_id=None,
                delete_row_ids=(),
                status="conflict",
                message="Duplicate group disappeared before repair planning completed.",
            )

        canonical_rows = [
            row for row in rows if row.get("business_key_hash") == canonical_hash
        ]
        if canonical_rows:
            keep_row = max(canonical_rows, key=lambda row: int(row["id"]))
        else:
            # Prefer the newest row because it normally carries the newest source_run/path
            # provenance while the source row content is guaranteed equal by source_row_hash.
            keep_row = max(rows, key=lambda row: int(row["id"]))
        keep_row_id = int(keep_row["id"])
        delete_row_ids = tuple(
            sorted(int(row["id"]) for row in rows if int(row["id"]) != keep_row_id)
        )
        return SettlementDuplicateRepairPlan(
            identity=identity,
            canonical_business_key_hash=canonical_hash,
            keep_row_id=keep_row_id,
            delete_row_ids=delete_row_ids,
            status="repairable",
            message=(
                "Exact source-identity duplicates can be collapsed safely; one canonical "
                "row will remain."
            ),
        )


def _identity_from_row(row: dict[str, Any]) -> SettlementDuplicateIdentity:
    return SettlementDuplicateIdentity(
        marketplace_id=str(row["marketplace_id"]),
        source_report_id=str(row["source_report_id"]),
        source_row_index=int(row["source_row_index"]),
        source_row_hash=str(row["source_row_hash"]),
        duplicate_count=int(row["duplicate_count"]),
    )


__all__ = [
    "SettlementDuplicateIdentity",
    "SettlementDuplicateRepairPlan",
    "SettlementIdempotencyRepairResult",
    "SettlementIdempotencyRepairService",
]
