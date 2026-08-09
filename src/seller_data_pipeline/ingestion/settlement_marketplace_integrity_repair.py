from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from seller_data_pipeline.db.connection import get_connection
from seller_data_pipeline.db.repositories.settlement_repo import SettlementRepo
from seller_data_pipeline.integrations.amazon.marketplaces import expected_marketplace_currency

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SettlementMarketplaceIntegrityPlan:
    source_report_id: str
    expected_currency: str
    observed_currencies: tuple[str, ...]
    row_count: int
    amount_total: Decimal
    raw_file_paths: tuple[str, ...]
    row_ids: tuple[int, ...]
    status: str
    message: str

    @property
    def requires_review(self) -> bool:
        return self.status == "conflict"

    @property
    def repairable(self) -> bool:
        return self.status == "repairable"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SettlementMarketplaceIntegrityRepairResult:
    mode: str
    status: str
    marketplace_id: str
    expected_currency: str
    scanned_row_count: int
    mismatched_report_count: int
    repairable_report_count: int
    conflict_report_count: int
    rows_to_delete: int
    rows_deleted: int
    plans: tuple[SettlementMarketplaceIntegrityPlan, ...]

    @property
    def requires_review(self) -> bool:
        return self.conflict_report_count > 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_summary_dict(self, *, sample_limit: int = 20) -> dict[str, Any]:
        conflicts = [plan.to_dict() for plan in self.plans if plan.requires_review]
        repairable = [plan.to_dict() for plan in self.plans if plan.repairable]
        return {
            "mode": self.mode,
            "status": self.status,
            "marketplace_id": self.marketplace_id,
            "expected_currency": self.expected_currency,
            "scanned_row_count": self.scanned_row_count,
            "mismatched_report_count": self.mismatched_report_count,
            "repairable_report_count": self.repairable_report_count,
            "conflict_report_count": self.conflict_report_count,
            "rows_to_delete": self.rows_to_delete,
            "rows_deleted": self.rows_deleted,
            "conflict_plan_sample": conflicts[:sample_limit],
            "repairable_plan_sample": repairable[:sample_limit],
            "plan_sample_limit": sample_limit,
        }


class SettlementMarketplaceIntegrityRepairService:
    """Audit and remove Settlement reports attributed to the wrong marketplace currency.

    This maintenance path is intentionally conservative. For a marketplace with a
    verified expected currency, an entire source report is repairable only when every
    non-empty currency in that report is the same *different* currency. Missing or mixed
    currencies are conflicts and block execute mode.
    """

    def run(
        self,
        *,
        marketplace_id: str,
        execute: bool = False,
    ) -> SettlementMarketplaceIntegrityRepairResult:
        expected_currency = expected_marketplace_currency(marketplace_id)
        if not expected_currency:
            raise ValueError(
                "No verified Settlement currency contract for marketplace "
                f"{marketplace_id}; marketplace integrity repair is unavailable."
            )

        LOGGER.info(
            "Settlement marketplace integrity scan started marketplace_id=%s expected_currency=%s mode=%s",
            marketplace_id,
            expected_currency,
            "execute" if execute else "dry_run",
        )
        with get_connection(autocommit=False) as conn:
            repo = SettlementRepo(conn)
            rows = repo.fetch_marketplace_integrity_rows(marketplace_id=marketplace_id)
            plans = build_marketplace_integrity_plans(
                rows=rows,
                expected_currency=expected_currency,
            )
            repairable = tuple(plan for plan in plans if plan.repairable)
            conflicts = tuple(plan for plan in plans if plan.requires_review)
            rows_to_delete = sum(len(plan.row_ids) for plan in repairable)

            if execute and conflicts:
                repo.rollback()
                LOGGER.warning(
                    "Settlement marketplace integrity repair blocked by %s conflict report(s).",
                    len(conflicts),
                )
                return SettlementMarketplaceIntegrityRepairResult(
                    mode="execute_blocked",
                    status="requires_review",
                    marketplace_id=marketplace_id,
                    expected_currency=expected_currency,
                    scanned_row_count=len(rows),
                    mismatched_report_count=len(plans),
                    repairable_report_count=len(repairable),
                    conflict_report_count=len(conflicts),
                    rows_to_delete=rows_to_delete,
                    rows_deleted=0,
                    plans=plans,
                )

            rows_deleted = 0
            if execute:
                delete_ids = [row_id for plan in repairable for row_id in plan.row_ids]
                try:
                    rows_deleted = repo.delete_transaction_rows_by_ids(delete_ids)
                    repo.commit()
                except Exception:
                    repo.rollback()
                    raise
            else:
                repo.rollback()

        status = "requires_review" if conflicts else "success"
        LOGGER.info(
            "Settlement marketplace integrity repair completed mode=%s status=%s "
            "mismatched_reports=%s repairable=%s conflicts=%s rows_deleted=%s",
            "execute" if execute else "dry_run",
            status,
            len(plans),
            len(repairable),
            len(conflicts),
            rows_deleted,
        )
        return SettlementMarketplaceIntegrityRepairResult(
            mode="execute" if execute else "dry_run",
            status=status,
            marketplace_id=marketplace_id,
            expected_currency=expected_currency,
            scanned_row_count=len(rows),
            mismatched_report_count=len(plans),
            repairable_report_count=len(repairable),
            conflict_report_count=len(conflicts),
            rows_to_delete=rows_to_delete,
            rows_deleted=rows_deleted,
            plans=plans,
        )


def build_marketplace_integrity_plans(
    *,
    rows: list[dict[str, Any]],
    expected_currency: str,
) -> tuple[SettlementMarketplaceIntegrityPlan, ...]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        report_id = row.get("source_report_id")
        if report_id is None:
            # Rows without an immutable source report identity cannot be safely deleted
            # by this report-level repair tool. Group them into an explicit conflict.
            report_id = "<missing-source-report-id>"
        grouped[str(report_id)].append(row)

    plans: list[SettlementMarketplaceIntegrityPlan] = []
    expected = expected_currency.upper()
    for report_id in sorted(grouped):
        report_rows = grouped[report_id]
        currencies = tuple(
            sorted(
                {
                    str(row.get("currency") or "").strip().upper()
                    for row in report_rows
                    if str(row.get("currency") or "").strip()
                }
            )
        )
        if currencies == (expected,):
            continue

        row_ids = tuple(sorted(int(row["id"]) for row in report_rows if row.get("id") is not None))
        paths = tuple(
            sorted(
                {
                    str(row.get("source_raw_file_path"))
                    for row in report_rows
                    if row.get("source_raw_file_path")
                }
            )
        )
        amount_total = sum(
            (Decimal(str(row.get("amount") or 0)) for row in report_rows),
            Decimal("0"),
        )

        if not currencies:
            status = "conflict"
            message = "Report has no non-empty currency; cannot verify marketplace attribution."
        elif len(currencies) == 1 and currencies[0] != expected:
            status = "repairable"
            message = (
                f"Whole report uses {currencies[0]} while marketplace expects {expected}; "
                "safe to remove from this marketplace after dry-run review."
            )
        else:
            status = "conflict"
            message = (
                f"Report contains mixed currencies {currencies}; cannot safely remove the whole report."
            )

        plans.append(
            SettlementMarketplaceIntegrityPlan(
                source_report_id=report_id,
                expected_currency=expected,
                observed_currencies=currencies,
                row_count=len(report_rows),
                amount_total=amount_total,
                raw_file_paths=paths,
                row_ids=row_ids,
                status=status,
                message=message,
            )
        )

    return tuple(plans)


__all__ = [
    "SettlementMarketplaceIntegrityPlan",
    "SettlementMarketplaceIntegrityRepairResult",
    "SettlementMarketplaceIntegrityRepairService",
    "build_marketplace_integrity_plans",
]
