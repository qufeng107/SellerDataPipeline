from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any

from seller_data_pipeline.db.connection import get_connection
from seller_data_pipeline.db.repositories.settlement_repo import SettlementRepo
from seller_data_pipeline.ingestion.settlement_table_mapping import (
    SETTLEMENT_TARGET_TABLE_SPEC,
    compute_business_key_hash,
)

LOGGER = logging.getLogger(__name__)


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
    keep_requires_hash_update: bool
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
    scanned_row_count: int
    duplicate_group_count: int
    repairable_group_count: int
    conflict_group_count: int
    rows_to_delete: int
    rows_deleted: int
    rows_to_rekey: int
    rows_rekeyed: int
    plans: tuple[SettlementDuplicateRepairPlan, ...]

    @property
    def requires_review(self) -> bool:
        return self.conflict_group_count > 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_summary_dict(self, *, sample_limit: int = 20) -> dict[str, Any]:
        conflicts = [plan.to_dict() for plan in self.plans if plan.requires_review]
        repairable = [plan.to_dict() for plan in self.plans if not plan.requires_review]
        return {
            "mode": self.mode,
            "status": self.status,
            "marketplace_id": self.marketplace_id,
            "scanned_row_count": self.scanned_row_count,
            "duplicate_group_count": self.duplicate_group_count,
            "repairable_group_count": self.repairable_group_count,
            "conflict_group_count": self.conflict_group_count,
            "rows_to_delete": self.rows_to_delete,
            "rows_deleted": self.rows_deleted,
            "rows_to_rekey": self.rows_to_rekey,
            "rows_rekeyed": self.rows_rekeyed,
            "conflict_plan_sample": conflicts[:sample_limit],
            "repairable_plan_sample": repairable[:sample_limit],
            "plan_sample_limit": sample_limit,
        }


class SettlementIdempotencyRepairService:
    """Audit and repair exact duplicate Settlement source rows.

    Planning is deliberately set-based: a single bounded table scan is loaded into
    memory and grouped locally. This avoids one or more SQL round trips per duplicate
    group, which is important because historical recovery can contain thousands of
    exact source-identity duplicates.

    The maintenance path remains intentionally narrow. It only touches rows whose
    immutable source identity is exactly equal:
    marketplace_id + source_report_id + source_row_index + source_row_hash.
    """

    def run(
        self,
        *,
        marketplace_id: str | None = None,
        execute: bool = False,
    ) -> SettlementIdempotencyRepairResult:
        LOGGER.info(
            "Settlement idempotency repair scan started. marketplace_id=%s mode=%s",
            marketplace_id or "ALL",
            "execute" if execute else "dry_run",
        )
        with get_connection(autocommit=False) as conn:
            repo = SettlementRepo(conn)
            rows = repo.fetch_idempotency_repair_rows(marketplace_id=marketplace_id)
            LOGGER.info(
                "Settlement idempotency repair scan loaded %s row(s).",
                len(rows),
            )

            plans = build_repair_plans(rows)
            conflicts = tuple(plan for plan in plans if plan.requires_review)
            repairable = tuple(plan for plan in plans if not plan.requires_review)
            rows_to_delete = sum(plan.rows_to_delete for plan in repairable)
            rows_to_rekey = sum(
                1
                for plan in repairable
                if plan.keep_row_id is not None and plan.keep_requires_hash_update
            )
            LOGGER.info(
                "Settlement idempotency repair planning completed. "
                "duplicate_groups=%s repairable=%s conflicts=%s "
                "rows_to_delete=%s rows_to_rekey=%s",
                len(plans),
                len(repairable),
                len(conflicts),
                rows_to_delete,
                rows_to_rekey,
            )

            if conflicts:
                repo.rollback()
                LOGGER.warning(
                    "Settlement idempotency repair blocked by %s conflict group(s).",
                    len(conflicts),
                )
                return SettlementIdempotencyRepairResult(
                    mode="execute_blocked" if execute else "dry_run",
                    status="requires_review",
                    marketplace_id=marketplace_id,
                    scanned_row_count=len(rows),
                    duplicate_group_count=len(plans),
                    repairable_group_count=len(repairable),
                    conflict_group_count=len(conflicts),
                    rows_to_delete=rows_to_delete,
                    rows_deleted=0,
                    rows_to_rekey=rows_to_rekey,
                    rows_rekeyed=0,
                    plans=plans,
                )

            rows_deleted = 0
            rows_rekeyed = 0
            if execute:
                delete_ids = [
                    row_id
                    for plan in repairable
                    for row_id in plan.delete_row_ids
                ]
                rekey_rows = [
                    (plan.keep_row_id, plan.canonical_business_key_hash)
                    for plan in repairable
                    if plan.keep_row_id is not None and plan.keep_requires_hash_update
                ]
                try:
                    if delete_ids:
                        LOGGER.info(
                            "Settlement idempotency repair deleting %s duplicate row(s).",
                            len(delete_ids),
                        )
                        rows_deleted = repo.delete_transaction_rows_by_ids(delete_ids)
                    if rekey_rows:
                        LOGGER.info(
                            "Settlement idempotency repair rekeying %s canonical row(s).",
                            len(rekey_rows),
                        )
                        rows_rekeyed = repo.update_transaction_business_key_hashes(rekey_rows)
                    repo.commit()
                except Exception:
                    repo.rollback()
                    raise
            else:
                repo.rollback()

        LOGGER.info(
            "Settlement idempotency repair completed. mode=%s status=success "
            "duplicate_groups=%s rows_deleted=%s rows_rekeyed=%s",
            "execute" if execute else "dry_run",
            len(plans),
            rows_deleted,
            rows_rekeyed,
        )
        return SettlementIdempotencyRepairResult(
            mode="execute" if execute else "dry_run",
            status="success",
            marketplace_id=marketplace_id,
            scanned_row_count=len(rows),
            duplicate_group_count=len(plans),
            repairable_group_count=len(repairable),
            conflict_group_count=0,
            rows_to_delete=rows_to_delete,
            rows_deleted=rows_deleted,
            rows_to_rekey=rows_to_rekey,
            rows_rekeyed=rows_rekeyed,
            plans=plans,
        )


def build_repair_plans(
    rows: list[dict[str, Any]],
) -> tuple[SettlementDuplicateRepairPlan, ...]:
    identity_rows: dict[tuple[str, str, int, str], list[dict[str, Any]]] = defaultdict(list)
    business_key_owners: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        business_key_hash = row.get("business_key_hash")
        if business_key_hash:
            business_key_owners[str(business_key_hash)].append(row)

        source_report_id = row.get("source_report_id")
        source_row_index = row.get("source_row_index")
        source_row_hash = row.get("source_row_hash")
        marketplace_id = row.get("marketplace_id")
        if (
            marketplace_id is None
            or source_report_id is None
            or source_row_index is None
            or source_row_hash is None
        ):
            continue
        identity_key = (
            str(marketplace_id),
            str(source_report_id),
            int(source_row_index),
            str(source_row_hash),
        )
        identity_rows[identity_key].append(row)

    plans: list[SettlementDuplicateRepairPlan] = []
    for identity_key in sorted(identity_rows):
        group_rows = identity_rows[identity_key]
        if len(group_rows) <= 1:
            continue
        identity = SettlementDuplicateIdentity(
            marketplace_id=identity_key[0],
            source_report_id=identity_key[1],
            source_row_index=identity_key[2],
            source_row_hash=identity_key[3],
            duplicate_count=len(group_rows),
        )
        canonical_hash = compute_business_key_hash(
            target_table=SETTLEMENT_TARGET_TABLE_SPEC.target_table,
            business_key_fields=SETTLEMENT_TARGET_TABLE_SPEC.business_key_fields,
            row=identity.as_key_row(),
        )
        owners = business_key_owners.get(canonical_hash, [])
        plans.append(
            _build_plan_from_rows(
                identity=identity,
                rows=group_rows,
                canonical_hash=canonical_hash,
                owners=owners,
            )
        )
    return tuple(plans)


def _build_plan_from_rows(
    *,
    identity: SettlementDuplicateIdentity,
    rows: list[dict[str, Any]],
    canonical_hash: str,
    owners: list[dict[str, Any]],
) -> SettlementDuplicateRepairPlan:
    if not rows:
        return SettlementDuplicateRepairPlan(
            identity=identity,
            canonical_business_key_hash=canonical_hash,
            keep_row_id=None,
            keep_requires_hash_update=False,
            delete_row_ids=(),
            status="conflict",
            message="Duplicate group disappeared before repair planning completed.",
        )

    group_ids = {int(row["id"]) for row in rows}
    external_owners = [row for row in owners if int(row["id"]) not in group_ids]
    if external_owners:
        return SettlementDuplicateRepairPlan(
            identity=identity,
            canonical_business_key_hash=canonical_hash,
            keep_row_id=None,
            keep_requires_hash_update=False,
            delete_row_ids=(),
            status="conflict",
            message=(
                "Canonical business key is owned by a different source identity; "
                "automatic repair was blocked."
            ),
        )

    canonical_rows = [
        row for row in rows if row.get("business_key_hash") == canonical_hash
    ]
    if len(canonical_rows) > 1:
        return SettlementDuplicateRepairPlan(
            identity=identity,
            canonical_business_key_hash=canonical_hash,
            keep_row_id=None,
            keep_requires_hash_update=False,
            delete_row_ids=(),
            status="conflict",
            message=(
                "Multiple rows in one source identity already own the canonical business key; "
                "automatic repair was blocked."
            ),
        )

    if canonical_rows:
        keep_row = canonical_rows[0]
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
        keep_requires_hash_update=keep_row.get("business_key_hash") != canonical_hash,
        delete_row_ids=delete_row_ids,
        status="repairable",
        message=(
            "Exact source-identity duplicates can be collapsed safely; one canonical "
            "row will remain."
        ),
    )


__all__ = [
    "SettlementDuplicateIdentity",
    "SettlementDuplicateRepairPlan",
    "SettlementIdempotencyRepairResult",
    "SettlementIdempotencyRepairService",
    "build_repair_plans",
]
