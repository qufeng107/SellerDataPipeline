from __future__ import annotations

import argparse
from datetime import UTC, date, datetime

from seller_data_pipeline.common.cli import run_cli_main
from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.db.connection import get_connection
from seller_data_pipeline.db.repositories.pipeline_artifact_repo import PipelineArtifactRepo
from seller_data_pipeline.services.automation_schedule_service import (
    AutomationScheduleService,
    monthly_artifact_scope,
    monthly_automation_window,
    weekly_artifact_scope,
    weekly_automation_window,
)
from seller_data_pipeline.services.pipeline_artifact_service import PipelineArtifactService

_ARTIFACT_PATHS = (
    "runtime/sampling",
    "reports/raw",
    "runtime/ingestion",
    "runtime/data_coverage_audits",
    "runtime/analysis_reports",
    "runtime/report_delivery",
)
_RESTORE_PREFIXES = (
    "runtime/sampling",
    "reports/raw",
    "runtime/analysis_reports",
    "runtime/report_delivery",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run one report-driven automation workflow phase. This wrapper restores/saves "
            "cross-job artifacts through Azure SQL for the free-first automation profile."
        )
    )
    parser.add_argument("--workflow", choices=["weekly", "monthly"], required=True)
    parser.add_argument("--phase", choices=["submit", "collect_ingest", "report_delivery"], required=True)
    parser.add_argument("--marketplace-id", default=None, help="Defaults to AMAZON_MARKETPLACE_ID.")
    parser.add_argument("--profile-id", default=None, help="Defaults to AMAZON_ADS_PROFILE_ID.")
    parser.add_argument(
        "--reference-date",
        default=None,
        help="Scheduler date, YYYY-MM-DD. Default: today UTC.",
    )
    parser.add_argument(
        "--week-start",
        default=None,
        help="Weekly report period start Saturday, YYYY-MM-DD. Default: auto.",
    )
    parser.add_argument("--month", default=None, help="Monthly report month YYYY-MM. Default: previous month.")
    parser.add_argument(
        "--send-email",
        action="store_true",
        help="For report_delivery, actually send email. Without this, send step is dry-run.",
    )
    parser.add_argument("--force-resend", action="store_true", help="Pass --force-resend to sender.")
    parser.add_argument(
        "--email-to",
        action="append",
        default=None,
        help=(
            "Temporary report email recipient override for report_delivery. "
            "Repeatable; comma-separated values are also accepted. Example: "
            "--email-to feng@cuidena.cn"
        ),
    )
    parser.add_argument(
        "--skip-artifact-store",
        action="store_true",
        help="Run commands without DB artifact restore/save. Useful for local troubleshooting only.",
    )
    parser.add_argument("--expires-days", type=int, default=90, help="Artifact retention days.")
    parser.add_argument("--max-file-mb", type=int, default=20, help="Max artifact file size MB.")
    parser.add_argument("--execute", action="store_true", help="Actually run commands and save artifacts.")
    parser.add_argument("--continue-on-error", action="store_true", help="Run remaining commands after failures.")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    marketplace_id = args.marketplace_id or settings.amazon_marketplace_id
    if not marketplace_id:
        raise SystemExit("Missing --marketplace-id or AMAZON_MARKETPLACE_ID.")
    profile_id = args.profile_id or settings.amazon_ads_profile_id
    reference_date = date.fromisoformat(args.reference_date) if args.reference_date else datetime.now(tz=UTC).date()
    week_start = date.fromisoformat(args.week_start) if args.week_start else None

    if args.workflow == "weekly":
        weekly_window = weekly_automation_window(reference_date, week_start=week_start)
        artifact_scope = weekly_artifact_scope(
            marketplace_id=marketplace_id,
            profile_id=profile_id,
            window=weekly_window,
        )
        print(
            "weekly_window="
            f"stats={weekly_window.stats_start}..{weekly_window.stats_end} "
            f"request={weekly_window.request_start}..{weekly_window.request_end}"
        )
    else:
        monthly_window = monthly_automation_window(reference_date, month=args.month)
        artifact_scope = monthly_artifact_scope(
            marketplace_id=marketplace_id,
            profile_id=profile_id,
            window=monthly_window,
        )
        print(f"monthly_window=month={monthly_window.month} range={monthly_window.start}..{monthly_window.end}")

    service = AutomationScheduleService()
    commands = service.build_commands(
        workflow=args.workflow,
        phase=args.phase,
        marketplace_id=marketplace_id,
        profile_id=profile_id,
        reference_date=reference_date,
        week_start=week_start,
        month=args.month,
        send_email=args.send_email,
        force_resend=args.force_resend,
        email_to=_split_email_values(args.email_to),
    )

    started_at = datetime.now(tz=UTC)
    artifact_service: PipelineArtifactService | None = None
    if not args.skip_artifact_store:
        connection_ctx = get_connection(settings=settings, autocommit=True)
        connection = connection_ctx.__enter__()
        artifact_service = PipelineArtifactService(repo=PipelineArtifactRepo(connection))
    else:
        connection_ctx = None

    try:
        if artifact_service and args.phase != "submit":
            restore = artifact_service.restore_scope(
                artifact_scope=artifact_scope,
                output_root=".",
                path_prefixes=_RESTORE_PREFIXES,
                dry_run=not args.execute,
            )
            print(
                f"artifact_restore scope={artifact_scope} "
                f"mode={'execute' if args.execute else 'dry_run'} restored={restore.restored_count}"
            )

        result = service.run(
            workflow=args.workflow,
            phase=args.phase,
            artifact_scope=artifact_scope,
            commands=commands,
            execute=args.execute,
            stop_on_error=not args.continue_on_error,
        )

        print(
            f"Automation stage workflow={result.workflow} phase={result.phase} "
            f"mode={'execute' if result.executed else 'dry_run'} scope={result.artifact_scope} "
            f"commands={len(result.commands)} failed={result.failed_count}"
        )
        for index, command in enumerate(result.commands, start=1):
            code_suffix = ""
            if result.executed and index <= len(result.return_codes):
                code_suffix = f" exit_code={result.return_codes[index - 1]}"
            print(f"{index}. {command.label}: {command.printable()}{code_suffix}")

        if artifact_service:
            save = artifact_service.save_paths(
                artifact_scope=artifact_scope,
                paths=list(_ARTIFACT_PATHS),
                root=".",
                modified_since=started_at,
                expires_days=args.expires_days,
                max_file_mb=args.max_file_mb,
                dry_run=not args.execute,
            )
            print(
                f"artifact_save scope={artifact_scope} "
                f"mode={'execute' if args.execute else 'dry_run'} scanned={save.scanned_count} "
                f"saved={save.saved_count} skipped={save.skipped_count}"
            )
        if result.executed and result.failed_count:
            raise SystemExit(1)
    finally:
        if connection_ctx is not None:
            connection_ctx.__exit__(None, None, None)


def _split_email_values(values: list[str] | None) -> tuple[str, ...]:
    if not values:
        return ()
    emails: list[str] = []
    for value in values:
        for item in value.split(","):
            email = item.strip()
            if email:
                emails.append(email)
    return tuple(dict.fromkeys(emails))


if __name__ == "__main__":
    run_cli_main(main)
