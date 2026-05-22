from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from typing import Literal

from seller_data_pipeline.integrations.amazon import report_types as rt

ManualRefreshPlanName = Literal["core_rolling", "weekly_full"]
ManualRefreshPhase = Literal["submit", "collect", "ingest", "audit"]


@dataclass(frozen=True)
class ManualRefreshCommand:
    """One concrete CLI command in a manual refresh plan."""

    label: str
    argv: tuple[str, ...]
    writes_external_or_database: bool = False

    def printable(self) -> str:
        return " ".join(["python", *self.argv])


@dataclass(frozen=True)
class ManualRefreshPlanResult:
    plan: str
    phase: str
    executed: bool
    commands: tuple[ManualRefreshCommand, ...]
    return_codes: tuple[int, ...]

    @property
    def failed_count(self) -> int:
        return sum(1 for code in self.return_codes if code != 0)


class ManualRefreshPlanService:
    """Build and optionally run standard manual data refresh command groups.

    This intentionally orchestrates existing scripts instead of duplicating ingestion logic.
    The goal is to make manual refresh repeatable now, then reuse the same fixed plan as
    the basis for scheduled Azure jobs later.
    """

    def build_commands(
        self,
        *,
        plan: ManualRefreshPlanName,
        phase: ManualRefreshPhase,
        marketplace_id: str,
        profile_id: str | None,
        target_start_date: str,
        force: bool = False,
    ) -> tuple[ManualRefreshCommand, ...]:
        if plan == "core_rolling":
            return _build_core_rolling_commands(
                phase=phase,
                marketplace_id=marketplace_id,
                profile_id=profile_id,
                target_start_date=target_start_date,
                force=force,
            )
        if plan == "weekly_full":
            return _build_weekly_full_commands(
                phase=phase,
                marketplace_id=marketplace_id,
                profile_id=profile_id,
                target_start_date=target_start_date,
                force=force,
            )
        raise ValueError(f"Unsupported manual refresh plan: {plan}")

    def run(
        self,
        *,
        plan: ManualRefreshPlanName,
        phase: ManualRefreshPhase,
        marketplace_id: str,
        profile_id: str | None,
        target_start_date: str,
        execute: bool = False,
        force: bool = False,
        stop_on_error: bool = True,
    ) -> ManualRefreshPlanResult:
        commands = self.build_commands(
            plan=plan,
            phase=phase,
            marketplace_id=marketplace_id,
            profile_id=profile_id,
            target_start_date=target_start_date,
            force=force,
        )
        if not execute:
            return ManualRefreshPlanResult(
                plan=plan,
                phase=phase,
                executed=False,
                commands=commands,
                return_codes=(),
            )

        return_codes: list[int] = []
        for command in commands:
            completed = subprocess.run([sys.executable, *command.argv], check=False)
            return_codes.append(completed.returncode)
            if completed.returncode != 0 and stop_on_error:
                break
        return ManualRefreshPlanResult(
            plan=plan,
            phase=phase,
            executed=True,
            commands=commands,
            return_codes=tuple(return_codes),
        )


def _build_core_rolling_commands(
    *,
    phase: ManualRefreshPhase,
    marketplace_id: str,
    profile_id: str | None,
    target_start_date: str,
    force: bool,
) -> tuple[ManualRefreshCommand, ...]:
    if phase == "submit":
        commands = [
            _submit_sp_report(rt.SALES_AND_TRAFFIC, marketplace_id, days=10),
            _submit_sp_report(rt.ALL_ORDERS_BY_ORDER_DATE, marketplace_id, days=10),
            _submit_sp_report(rt.INVENTORY, marketplace_id, days=None),
            _run_ads_sampling_plan(profile_id=profile_id, days=14, force=True),
            _run_sampling_plan(
                marketplace_id=marketplace_id,
                report_types=(rt.PROMOTION_PERFORMANCE, rt.COUPON_PERFORMANCE),
                force=True,
            ),
        ]
        return tuple(commands)
    if phase == "collect":
        return (
            ManualRefreshCommand(
                label="Collect ready SP-API reports",
                argv=("scripts/collect_ready_reports.py", "--limit", "50"),
            ),
            ManualRefreshCommand(
                label="Collect ready Amazon Ads reports",
                argv=("scripts/collect_ads_reports.py", "--limit", "50"),
            ),
        )
    if phase == "ingest":
        return (
            _ingest("Sales & Traffic", "scripts/ingest_sales_traffic_report.py", marketplace_id),
            _ingest("Orders", "scripts/ingest_orders_report.py", marketplace_id),
            _ingest_ads(profile_id=profile_id, marketplace_id=marketplace_id),
            _ingest("Promotion/Coupon", "scripts/ingest_promotion_coupon_reports.py", marketplace_id),
            _ingest("Inventory snapshot", "scripts/ingest_inventory_snapshot.py", marketplace_id),
        )
    if phase == "audit":
        return (_audit(marketplace_id=marketplace_id, target_start_date=target_start_date),)
    raise ValueError(f"Unsupported phase: {phase}")


def _build_weekly_full_commands(
    *,
    phase: ManualRefreshPhase,
    marketplace_id: str,
    profile_id: str | None,
    target_start_date: str,
    force: bool,
) -> tuple[ManualRefreshCommand, ...]:
    core_commands = _build_core_rolling_commands(
        phase=phase,
        marketplace_id=marketplace_id,
        profile_id=profile_id,
        target_start_date=target_start_date,
        force=force,
    )
    if phase in {"collect", "audit"}:
        return core_commands
    if phase == "submit":
        slow_commands = (
            _run_sampling_plan(
                marketplace_id=marketplace_id,
                report_types=(rt.SETTLEMENT_V2,),
                force=True,
                extra=("--discovery-page-size", "100", "--discovery-max-pages", "10"),
            ),
            _submit_sp_report(rt.FBA_REIMBURSEMENTS, marketplace_id, days=60),
            _run_sampling_plan(
                marketplace_id=marketplace_id,
                report_types=(rt.LEDGER_SUMMARY_VIEW, rt.LEDGER_DETAIL_VIEW),
                force=True,
            ),
            _submit_sp_report(rt.LISTINGS_ALL_DATA, marketplace_id, days=None),
            _submit_sp_report(rt.FBA_ESTIMATED_FEES, marketplace_id, days=4),
        )
        return (*core_commands, *slow_commands)
    if phase == "ingest":
        slow_commands = (
            _ingest("Settlement", "scripts/ingest_settlement_report.py", marketplace_id),
            _ingest(
                "FBA reimbursements",
                "scripts/ingest_fba_reimbursements_report.py",
                marketplace_id,
            ),
            _ingest(
                "Inventory ledger",
                "scripts/ingest_inventory_ledger_reports.py",
                marketplace_id,
            ),
            _ingest("Listing snapshot", "scripts/ingest_listing_snapshot.py", marketplace_id),
            _ingest(
                "FBA fee preview",
                "scripts/ingest_fba_fee_preview_report.py",
                marketplace_id,
            ),
        )
        return (*core_commands, *slow_commands)
    raise ValueError(f"Unsupported phase: {phase}")


def _submit_sp_report(
    report_type: str,
    marketplace_id: str,
    *,
    days: int | None,
) -> ManualRefreshCommand:
    argv = [
        "scripts/submit_report_requests.py",
        "--marketplace-id",
        marketplace_id,
        "--report-type",
        report_type,
    ]
    if days is not None:
        argv.extend(["--days", str(days)])
    return ManualRefreshCommand(
        label=f"Submit SP-API report {report_type}",
        argv=tuple(argv),
        writes_external_or_database=True,
    )


def _run_sampling_plan(
    *,
    marketplace_id: str,
    report_types: tuple[str, ...],
    force: bool,
    extra: tuple[str, ...] = (),
) -> ManualRefreshCommand:
    argv = ["scripts/run_sampling_plan.py", "--marketplace-id", marketplace_id]
    for report_type in report_types:
        argv.extend(["--only-report-type", report_type])
    if force:
        argv.append("--force")
    argv.extend(extra)
    return ManualRefreshCommand(
        label="Submit/discover SP-API sampling plan: " + ", ".join(report_types),
        argv=tuple(argv),
        writes_external_or_database=True,
    )


def _run_ads_sampling_plan(
    *,
    profile_id: str | None,
    days: int,
    force: bool,
) -> ManualRefreshCommand:
    argv = ["scripts/run_ads_sampling_plan.py", "--days", str(days)]
    if profile_id:
        argv.extend(["--profile-id", profile_id])
    if force:
        argv.append("--force")
    return ManualRefreshCommand(
        label="Submit Amazon Ads rolling reports",
        argv=tuple(argv),
        writes_external_or_database=True,
    )


def _ingest(label: str, script_path: str, marketplace_id: str) -> ManualRefreshCommand:
    return ManualRefreshCommand(
        label=f"Ingest {label}",
        argv=(script_path, "--marketplace-id", marketplace_id, "--execute"),
        writes_external_or_database=True,
    )


def _ingest_ads(*, profile_id: str | None, marketplace_id: str) -> ManualRefreshCommand:
    argv = ["scripts/ingest_ads_reports.py", "--marketplace-id", marketplace_id, "--execute"]
    if profile_id:
        argv.extend(["--profile-id", profile_id])
    return ManualRefreshCommand(
        label="Ingest Amazon Ads",
        argv=tuple(argv),
        writes_external_or_database=True,
    )


def _audit(*, marketplace_id: str, target_start_date: str) -> ManualRefreshCommand:
    return ManualRefreshCommand(
        label="Audit normalized data coverage",
        argv=(
            "scripts/audit_data_coverage.py",
            "--marketplace-id",
            marketplace_id,
            "--target-start-date",
            target_start_date,
        ),
    )
