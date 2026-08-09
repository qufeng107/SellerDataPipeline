from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

from seller_data_pipeline.integrations.amazon import report_types as rt

AutomationWorkflow = Literal["weekly", "monthly"]
AutomationPhase = Literal["submit", "collect_ingest", "report_delivery"]
AutomationReport = Literal[
    "weekly_business_review",
    "weekly_ads_optimization",
    "monthly_financial_close",
]


@dataclass(frozen=True)
class WeeklyAutomationWindow:
    stats_start: date
    stats_end: date
    request_start: date
    request_end: date

    @property
    def period_key(self) -> str:
        return f"{self.stats_start.isoformat()}_{self.stats_end.isoformat()}"


@dataclass(frozen=True)
class MonthlyAutomationWindow:
    month: str
    start: date
    end: date


@dataclass(frozen=True)
class AutomationCommand:
    label: str
    argv: tuple[str, ...]
    writes_external_or_database: bool = False

    def printable(self) -> str:
        return " ".join(["python", *self.argv])


@dataclass(frozen=True)
class AutomationCommandExecution:
    command_index: int
    command: AutomationCommand
    started_at: datetime | None
    finished_at: datetime | None
    exit_code: int | None
    duration_ms: int | None


@dataclass(frozen=True)
class AutomationRunResult:
    workflow: str
    phase: str
    executed: bool
    artifact_scope: str
    commands: tuple[AutomationCommand, ...]
    return_codes: tuple[int, ...]
    command_executions: tuple[AutomationCommandExecution, ...] = ()

    @property
    def failed_count(self) -> int:
        return sum(1 for code in self.return_codes if code != 0)


CommandStartedCallback = Callable[[int, AutomationCommand, datetime], Any]
CommandFinishedCallback = Callable[[Any, int | None, datetime], None]


class AutomationScheduleService:
    """Build report-driven automation commands for the free-first cloud workflow."""

    def build_commands(
        self,
        *,
        workflow: AutomationWorkflow,
        phase: AutomationPhase,
        marketplace_id: str,
        profile_id: str | None,
        reference_date: date,
        week_start: date | None = None,
        month: str | None = None,
        send_email: bool = False,
        force_resend: bool = False,
        email_to: tuple[str, ...] = (),
    ) -> tuple[AutomationCommand, ...]:
        if workflow == "weekly":
            window = weekly_automation_window(reference_date, week_start=week_start)
            return _weekly_commands(
                phase=phase,
                window=window,
                marketplace_id=marketplace_id,
                profile_id=profile_id,
                send_email=send_email,
                force_resend=force_resend,
                email_to=email_to,
            )
        if workflow == "monthly":
            window = monthly_automation_window(reference_date, month=month)
            return _monthly_commands(
                phase=phase,
                window=window,
                marketplace_id=marketplace_id,
                profile_id=profile_id,
                send_email=send_email,
                force_resend=force_resend,
                email_to=email_to,
            )
        raise ValueError(f"Unsupported workflow: {workflow}")

    def run(
        self,
        *,
        workflow: AutomationWorkflow,
        phase: AutomationPhase,
        artifact_scope: str,
        commands: tuple[AutomationCommand, ...],
        execute: bool,
        stop_on_error: bool = True,
        command_started: CommandStartedCallback | None = None,
        command_finished: CommandFinishedCallback | None = None,
    ) -> AutomationRunResult:
        if not execute:
            return AutomationRunResult(
                workflow=workflow,
                phase=phase,
                executed=False,
                artifact_scope=artifact_scope,
                commands=commands,
                return_codes=(),
                command_executions=tuple(
                    AutomationCommandExecution(
                        command_index=index,
                        command=command,
                        started_at=None,
                        finished_at=None,
                        exit_code=None,
                        duration_ms=None,
                    )
                    for index, command in enumerate(commands, start=1)
                ),
            )
        return_codes: list[int] = []
        executions: list[AutomationCommandExecution] = []
        for index, command in enumerate(commands, start=1):
            started_at = datetime.now(tz=UTC)
            handle = command_started(index, command, started_at) if command_started else None
            completed = subprocess.run([sys.executable, *command.argv], check=False)
            finished_at = datetime.now(tz=UTC)
            duration_ms = max(0, int((finished_at - started_at).total_seconds() * 1000))
            return_codes.append(completed.returncode)
            executions.append(
                AutomationCommandExecution(
                    command_index=index,
                    command=command,
                    started_at=started_at,
                    finished_at=finished_at,
                    exit_code=completed.returncode,
                    duration_ms=duration_ms,
                )
            )
            if command_finished:
                command_finished(handle, completed.returncode, finished_at)
            if completed.returncode != 0 and stop_on_error:
                break
        return AutomationRunResult(
            workflow=workflow,
            phase=phase,
            executed=True,
            artifact_scope=artifact_scope,
            commands=commands,
            return_codes=tuple(return_codes),
            command_executions=tuple(executions),
        )


def weekly_automation_window(
    reference_date: date,
    *,
    week_start: date | None = None,
    stable_lag_days: int = 2,
    request_buffer_days: int = 3,
) -> WeeklyAutomationWindow:
    """Return the Saturday-Friday report period and buffered request window.

    Scheduled weekly jobs run on Monday. The latest stable reporting week is the
    Saturday-Friday period ending on the most recent Friday that is at least
    stable_lag_days before reference_date. The data request window starts three days
    earlier on Wednesday to give overlapping backfill coverage.
    """

    if week_start is not None:
        if week_start.weekday() != 5:
            raise ValueError("weekly automation week_start must be a Saturday")
        stats_start = week_start
        stats_end = week_start + timedelta(days=6)
    else:
        latest_allowed = reference_date - timedelta(days=stable_lag_days)
        days_since_friday = (latest_allowed.weekday() - 4) % 7
        stats_end = latest_allowed - timedelta(days=days_since_friday)
        stats_start = stats_end - timedelta(days=6)
    return WeeklyAutomationWindow(
        stats_start=stats_start,
        stats_end=stats_end,
        request_start=stats_start - timedelta(days=request_buffer_days),
        request_end=stats_end,
    )


def monthly_automation_window(
    reference_date: date, *, month: str | None = None
) -> MonthlyAutomationWindow:
    if month is not None:
        year, month_number = _parse_month(month)
    else:
        first_this_month = reference_date.replace(day=1)
        last_previous_month = first_this_month - timedelta(days=1)
        year = last_previous_month.year
        month_number = last_previous_month.month
    start = date(year, month_number, 1)
    next_month = date(
        year + (1 if month_number == 12 else 0), 1 if month_number == 12 else month_number + 1, 1
    )
    end = next_month - timedelta(days=1)
    return MonthlyAutomationWindow(month=f"{year:04d}-{month_number:02d}", start=start, end=end)


def weekly_artifact_scope(
    *, marketplace_id: str, profile_id: str | None, window: WeeklyAutomationWindow
) -> str:
    profile = profile_id or "no_profile"
    return f"weekly:{marketplace_id}:{profile}:{window.period_key}"


def monthly_artifact_scope(
    *, marketplace_id: str, profile_id: str | None, window: MonthlyAutomationWindow
) -> str:
    profile = profile_id or "no_profile"
    return f"monthly:{marketplace_id}:{profile}:{window.month}"


def _weekly_commands(
    *,
    phase: AutomationPhase,
    window: WeeklyAutomationWindow,
    marketplace_id: str,
    profile_id: str | None,
    send_email: bool,
    force_resend: bool,
    email_to: tuple[str, ...] = (),
) -> tuple[AutomationCommand, ...]:
    if phase == "submit":
        commands = [
            _backfill_sp(
                rt.SALES_AND_TRAFFIC, marketplace_id, window.request_start, window.request_end, 10
            ),
            _backfill_sp(
                rt.ALL_ORDERS_BY_ORDER_DATE,
                marketplace_id,
                window.request_start,
                window.request_end,
                10,
            ),
            _submit_sp(rt.INVENTORY, marketplace_id),
            _backfill_ads(profile_id, window.request_start, window.request_end, 10),
        ]
        return tuple(command for command in commands if command is not None)
    if phase == "collect_ingest":
        return (
            _command(
                "Collect ready SP-API reports",
                ("scripts/collect_ready_reports.py", "--limit", "50"),
            ),
            _command(
                "Collect ready Amazon Ads reports",
                ("scripts/collect_ads_reports.py", "--limit", "50"),
            ),
            _ingest("Sales & Traffic", "scripts/ingest_sales_traffic_report.py", marketplace_id),
            _ingest("Orders", "scripts/ingest_orders_report.py", marketplace_id),
            _ingest_ads(profile_id=profile_id, marketplace_id=marketplace_id),
            _ingest("Inventory snapshot", "scripts/ingest_inventory_snapshot.py", marketplace_id),
            _command(
                "Audit normalized data coverage",
                (
                    "scripts/audit_data_coverage.py",
                    "--marketplace-id",
                    marketplace_id,
                    "--target-start-date",
                    window.stats_start.isoformat(),
                ),
            ),
        )
    if phase == "report_delivery":
        week_start = window.stats_start.isoformat()
        return (
            _report_weekly_business(marketplace_id, profile_id, week_start),
            _delivery_pack(
                _weekly_business_json_path(marketplace_id, window),
                "operations",
            ),
            _send_pack(
                _weekly_business_pack_path(marketplace_id, profile_id, window),
                "operations",
                send_email,
                force_resend,
                email_to=email_to,
            ),
            _report_weekly_ads(marketplace_id, profile_id, week_start),
            _delivery_pack(
                _weekly_ads_json_path(profile_id, window),
                "ads_operator",
            ),
            _send_pack(
                _weekly_ads_pack_path(marketplace_id, profile_id, window),
                "ads_operator",
                send_email,
                force_resend,
                email_to=email_to,
            ),
        )
    raise ValueError(f"Unsupported phase: {phase}")


def _monthly_commands(
    *,
    phase: AutomationPhase,
    window: MonthlyAutomationWindow,
    marketplace_id: str,
    profile_id: str | None,
    send_email: bool,
    force_resend: bool,
    email_to: tuple[str, ...] = (),
) -> tuple[AutomationCommand, ...]:
    if phase == "submit":
        commands = [
            _backfill_sp(rt.SALES_AND_TRAFFIC, marketplace_id, window.start, window.end, 14),
            _backfill_sp(rt.ALL_ORDERS_BY_ORDER_DATE, marketplace_id, window.start, window.end, 14),
            _backfill_sp(rt.FBA_REIMBURSEMENTS, marketplace_id, window.start, window.end, 31),
            _backfill_ads(profile_id, window.start, window.end, 14),
            _run_sampling_plan(
                marketplace_id,
                (rt.SETTLEMENT_V2,),
                extra=("--discovery-page-size", "100", "--discovery-max-pages", "10"),
            ),
            _run_sampling_plan(marketplace_id, (rt.PROMOTION_PERFORMANCE, rt.COUPON_PERFORMANCE)),
        ]
        return tuple(command for command in commands if command is not None)
    if phase == "collect_ingest":
        return (
            # Settlement reports are Amazon-generated and can appear several days after
            # month-end transactions are posted/released. Rediscover on every monthly
            # collect run so a rerun can pick up late settlements before final close.
            _run_sampling_plan(
                marketplace_id,
                (rt.SETTLEMENT_V2,),
                extra=(
                    "--discovery-page-size",
                    "100",
                    "--discovery-max-pages",
                    "10",
                    "--fail-on-error",
                ),
            ),
            _command(
                "Collect ready SP-API reports",
                ("scripts/collect_ready_reports.py", "--limit", "100"),
            ),
            _command(
                "Collect ready Amazon Ads reports",
                ("scripts/collect_ads_reports.py", "--limit", "100"),
            ),
            _ingest(
                "Sales & Traffic",
                "scripts/ingest_sales_traffic_report.py",
                marketplace_id,
                start_date=window.start,
                end_date=window.end,
            ),
            _ingest(
                "Orders",
                "scripts/ingest_orders_report.py",
                marketplace_id,
                start_date=window.start,
                end_date=window.end,
            ),
            _ingest_ads(
                profile_id=profile_id,
                marketplace_id=marketplace_id,
                start_date=window.start,
                end_date=window.end,
            ),
            _ingest("Settlement", "scripts/ingest_settlement_report.py", marketplace_id),
            _ingest(
                "FBA reimbursements", "scripts/ingest_fba_reimbursements_report.py", marketplace_id
            ),
            _ingest(
                "Promotion/Coupon", "scripts/ingest_promotion_coupon_reports.py", marketplace_id
            ),
            _command(
                "Audit normalized data coverage",
                (
                    "scripts/audit_data_coverage.py",
                    "--marketplace-id",
                    marketplace_id,
                    "--target-start-date",
                    window.start.isoformat(),
                    "--target-end-date",
                    window.end.isoformat(),
                ),
            ),
        )
    if phase == "report_delivery":
        return (
            _report_monthly_close(marketplace_id, profile_id, window.month),
            _delivery_pack(_monthly_close_json_path(marketplace_id, window), "shareholders"),
            _send_pack(
                _monthly_close_pack_path(marketplace_id, profile_id, window),
                "shareholders",
                send_email,
                force_resend,
                email_to=email_to,
            ),
        )
    raise ValueError(f"Unsupported phase: {phase}")


def _command(label: str, argv: tuple[str, ...], *, writes: bool = False) -> AutomationCommand:
    return AutomationCommand(label=label, argv=argv, writes_external_or_database=writes)


def _backfill_sp(
    report_type: str, marketplace_id: str, start: date, end: date, chunk_days: int
) -> AutomationCommand:
    return _command(
        f"Submit SP-API backfill {report_type} {start}..{end}",
        (
            "scripts/backfill_report_requests.py",
            "--marketplace-id",
            marketplace_id,
            "--report-type",
            report_type,
            "--start-date",
            start.isoformat(),
            "--end-date",
            end.isoformat(),
            "--chunk-days",
            str(chunk_days),
            "--execute",
        ),
        writes=True,
    )


def _backfill_ads(
    profile_id: str | None, start: date, end: date, chunk_days: int
) -> AutomationCommand | None:
    if not profile_id:
        return None
    return _command(
        f"Submit Amazon Ads backfill {start}..{end}",
        (
            "scripts/backfill_ads_reports.py",
            "--profile-id",
            profile_id,
            "--start-date",
            start.isoformat(),
            "--end-date",
            end.isoformat(),
            "--chunk-days",
            str(chunk_days),
            "--execute",
        ),
        writes=True,
    )


def _submit_sp(report_type: str, marketplace_id: str) -> AutomationCommand:
    return _command(
        f"Submit SP-API report {report_type}",
        (
            "scripts/submit_report_requests.py",
            "--marketplace-id",
            marketplace_id,
            "--report-type",
            report_type,
        ),
        writes=True,
    )


def _run_sampling_plan(
    marketplace_id: str,
    report_types: tuple[str, ...],
    *,
    extra: tuple[str, ...] = (),
) -> AutomationCommand:
    argv = ["scripts/run_sampling_plan.py", "--marketplace-id", marketplace_id]
    for report_type in report_types:
        argv.extend(["--only-report-type", report_type])
    argv.append("--force")
    argv.extend(extra)
    return _command(
        "Submit/discover SP-API sampling plan: " + ", ".join(report_types), tuple(argv), writes=True
    )


def _ingest(
    label: str,
    script_path: str,
    marketplace_id: str,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> AutomationCommand:
    argv = [script_path, "--marketplace-id", marketplace_id]
    if start_date is not None or end_date is not None:
        if start_date is None or end_date is None:
            raise ValueError("start_date and end_date must be provided together")
        argv.extend(["--start-date", start_date.isoformat(), "--end-date", end_date.isoformat()])
    argv.append("--execute")
    return _command(f"Ingest {label}", tuple(argv), writes=True)


def _ingest_ads(
    *,
    profile_id: str | None,
    marketplace_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> AutomationCommand:
    argv = ["scripts/ingest_ads_reports.py", "--marketplace-id", marketplace_id]
    if profile_id:
        argv.extend(["--profile-id", profile_id])
    if start_date is not None or end_date is not None:
        if start_date is None or end_date is None:
            raise ValueError("start_date and end_date must be provided together")
        argv.extend(["--start-date", start_date.isoformat(), "--end-date", end_date.isoformat()])
    argv.append("--execute")
    return _command("Ingest Amazon Ads", tuple(argv), writes=True)


def _report_weekly_business(
    marketplace_id: str, profile_id: str | None, week_start: str
) -> AutomationCommand:
    argv = [
        "scripts/generate_weekly_business_review.py",
        "--marketplace-id",
        marketplace_id,
        "--week-start",
        week_start,
        "--dry-run",
    ]
    if profile_id:
        argv.extend(["--profile-id", profile_id])
    return _command("Generate Weekly Business Review", tuple(argv))


def _report_weekly_ads(
    marketplace_id: str, profile_id: str | None, week_start: str
) -> AutomationCommand:
    argv = [
        "scripts/generate_weekly_ads_optimization_report.py",
        "--marketplace-id",
        marketplace_id,
        "--week-start",
        week_start,
        "--dry-run",
    ]
    if profile_id:
        argv.extend(["--profile-id", profile_id])
    return _command("Generate Weekly Ads Optimization Report", tuple(argv))


def _report_monthly_close(
    marketplace_id: str, profile_id: str | None, month: str
) -> AutomationCommand:
    argv = [
        "scripts/generate_monthly_financial_close_report.py",
        "--marketplace-id",
        marketplace_id,
        "--month",
        month,
        "--dry-run",
    ]
    if profile_id:
        argv.extend(["--profile-id", profile_id])
    return _command("Generate Monthly Financial Close", tuple(argv))


def _delivery_pack(report_json: str, audience: str) -> AutomationCommand:
    return _command(
        f"Generate report delivery pack for {audience}",
        (
            "scripts/generate_report_delivery_pack.py",
            "--report-json",
            report_json,
            "--audience",
            audience,
            "--dry-run",
        ),
    )


def _send_pack(
    pack_dir: str,
    audience: str,
    send_email: bool,
    force_resend: bool,
    *,
    email_to: tuple[str, ...] = (),
) -> AutomationCommand:
    argv = [
        "scripts/send_report_email.py",
        "--delivery-pack",
        pack_dir,
        "--audience",
        audience,
        "--execute" if send_email else "--dry-run",
    ]
    if force_resend:
        argv.append("--force-resend")
    for email in email_to:
        argv.extend(["--to", email])
    return _command(
        f"{'Send' if send_email else 'Validate'} report email for {audience}",
        tuple(argv),
        writes=send_email,
    )


def _weekly_business_json_path(marketplace_id: str, window: WeeklyAutomationWindow) -> str:
    return (
        f"runtime/analysis_reports/weekly_business_review/{marketplace_id}/{window.period_key}/"
        f"weekly_business_review_{window.period_key}.json"
    )


def _weekly_ads_json_path(profile_id: str | None, window: WeeklyAutomationWindow) -> str:
    profile = profile_id or "no_profile"
    return (
        f"runtime/analysis_reports/weekly_ads_optimization/{profile}/"
        f"{window.period_key}/weekly_ads_optimization_{window.period_key}.json"
    )


def _monthly_close_json_path(marketplace_id: str, window: MonthlyAutomationWindow) -> str:
    return (
        f"runtime/analysis_reports/monthly_financial_close/{marketplace_id}/{window.month}/"
        f"monthly_financial_close_{window.month}.json"
    )


def _delivery_scope(marketplace_id: str, profile_id: str | None) -> str:
    return f"{marketplace_id}_{profile_id or 'no_profile'}"


def _weekly_business_pack_path(
    marketplace_id: str, profile_id: str | None, window: WeeklyAutomationWindow
) -> str:
    scope = _delivery_scope(marketplace_id, profile_id)
    return f"runtime/report_delivery/weekly_business_review/{scope}/{window.period_key}"


def _weekly_ads_pack_path(
    marketplace_id: str, profile_id: str | None, window: WeeklyAutomationWindow
) -> str:
    scope = _delivery_scope(marketplace_id, profile_id)
    return f"runtime/report_delivery/weekly_ads_optimization/{scope}/{window.period_key}"


def _monthly_close_pack_path(
    marketplace_id: str, profile_id: str | None, window: MonthlyAutomationWindow
) -> str:
    scope = _delivery_scope(marketplace_id, profile_id)
    return f"runtime/report_delivery/monthly_financial_close/{scope}/{window.month}"


def _parse_month(value: str) -> tuple[int, int]:
    parts = value.split("-")
    if len(parts) != 2:
        raise ValueError("month must use YYYY-MM format")
    year = int(parts[0])
    month_number = int(parts[1])
    if month_number < 1 or month_number > 12:
        raise ValueError("month must use YYYY-MM format")
    return year, month_number
