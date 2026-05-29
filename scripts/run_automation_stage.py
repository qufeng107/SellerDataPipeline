from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
from pathlib import Path

from seller_data_pipeline.common.cli import run_cli_main
from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.db.connection import get_connection
from seller_data_pipeline.db.repositories.pipeline_artifact_repo import PipelineArtifactRepo
from seller_data_pipeline.db.repositories.pipeline_job_audit_repo import PipelineJobAuditRepo
from seller_data_pipeline.services.automation_schedule_service import (
    AutomationScheduleService,
    monthly_artifact_scope,
    monthly_automation_window,
    weekly_artifact_scope,
    weekly_automation_window,
)
from seller_data_pipeline.services.pipeline_artifact_service import PipelineArtifactService
from seller_data_pipeline.services.pipeline_job_audit_service import (
    AutomationAuditContext,
    AutomationAuditWindow,
    PipelineJobAuditService,
    build_config_snapshot,
    command_line_hash,
    resolve_trigger_value,
)

_ARTIFACT_PATHS = (
    "runtime/sampling",
    "reports/raw",
    "runtime/ingestion",
    "runtime/data_coverage_audits",
    "runtime/analysis_reports",
    "runtime/report_delivery",
    "runtime/automation_audit",
)
_RESTORE_PREFIXES = (
    "runtime/sampling",
    "reports/raw",
    "runtime/analysis_reports",
    "runtime/report_delivery",
    "runtime/automation_audit",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run one report-driven automation workflow phase. This wrapper restores/saves "
            "cross-job artifacts through Azure SQL for the free-first automation profile."
        )
    )
    parser.add_argument("--workflow", choices=["weekly", "monthly"], required=True)
    parser.add_argument(
        "--phase", choices=["submit", "collect_ingest", "report_delivery"], required=True
    )
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
    parser.add_argument(
        "--month", default=None, help="Monthly report month YYYY-MM. Default: previous month."
    )
    parser.add_argument(
        "--send-email",
        action="store_true",
        help="For report_delivery, actually send email. Without this, send step is dry-run.",
    )
    parser.add_argument(
        "--force-resend", action="store_true", help="Pass --force-resend to sender."
    )
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
        help=(
            "Run commands without DB artifact restore/save. "
            "Useful for local troubleshooting only."
        ),
    )
    parser.add_argument(
        "--skip-audit-log",
        action="store_true",
        help="Disable structured pipeline_job_* SQL audit writes for this wrapper run.",
    )
    parser.add_argument(
        "--configured-trigger-type",
        default=None,
        help=(
            "Configured Azure Job trigger type, for audit only. "
            "Defaults to SDP_CONFIGURED_TRIGGER_TYPE when set."
        ),
    )
    parser.add_argument(
        "--run-trigger-type",
        default=None,
        help=(
            "Best-effort actual run trigger, for audit only: schedule/manual/event/unknown. "
            "Defaults to SDP_RUN_TRIGGER_TYPE when set."
        ),
    )
    parser.add_argument("--expires-days", type=int, default=90, help="Artifact retention days.")
    parser.add_argument("--max-file-mb", type=int, default=20, help="Max artifact file size MB.")
    parser.add_argument(
        "--execute", action="store_true", help="Actually run commands and save artifacts."
    )
    parser.add_argument(
        "--continue-on-error", action="store_true", help="Run remaining commands after failures."
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    marketplace_id = args.marketplace_id or settings.amazon_marketplace_id
    if not marketplace_id:
        raise SystemExit("Missing --marketplace-id or AMAZON_MARKETPLACE_ID.")
    profile_id = args.profile_id or settings.amazon_ads_profile_id
    reference_date = (
        date.fromisoformat(args.reference_date)
        if args.reference_date
        else datetime.now(tz=UTC).date()
    )
    week_start = date.fromisoformat(args.week_start) if args.week_start else None

    if args.workflow == "weekly":
        weekly_window = weekly_automation_window(reference_date, week_start=week_start)
        artifact_scope = weekly_artifact_scope(
            marketplace_id=marketplace_id,
            profile_id=profile_id,
            window=weekly_window,
        )
        audit_window = AutomationAuditWindow(
            period_key=weekly_window.period_key,
            stats_start=weekly_window.stats_start,
            stats_end=weekly_window.stats_end,
            request_start=weekly_window.request_start,
            request_end=weekly_window.request_end,
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
        audit_window = AutomationAuditWindow(
            period_key=monthly_window.month,
            stats_start=monthly_window.start,
            stats_end=monthly_window.end,
            request_start=monthly_window.start,
            request_end=monthly_window.end,
        )
        print(
            f"monthly_window=month={monthly_window.month} "
            f"range={monthly_window.start}..{monthly_window.end}"
        )

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
    configured_trigger_type, configured_trigger_source = resolve_trigger_value(
        args.configured_trigger_type, env_name="SDP_CONFIGURED_TRIGGER_TYPE"
    )
    run_trigger_type, run_trigger_source = resolve_trigger_value(
        args.run_trigger_type, env_name="SDP_RUN_TRIGGER_TYPE"
    )
    trigger_source_parts = [
        f"configured={configured_trigger_source}",
        f"run={run_trigger_source}",
    ]
    artifact_service: PipelineArtifactService | None = None
    audit_service: PipelineJobAuditService | None = None
    if not args.skip_artifact_store:
        connection_ctx = get_connection(settings=settings, autocommit=True)
        connection = connection_ctx.__enter__()
        artifact_service = PipelineArtifactService(repo=PipelineArtifactRepo(connection))
        if not args.skip_audit_log:
            audit_service = PipelineJobAuditService(repo=PipelineJobAuditRepo(connection))
            audit_service.start_run(
                AutomationAuditContext(
                    workflow=args.workflow,
                    phase=args.phase,
                    execution_mode="execute" if args.execute else "dry_run",
                    configured_trigger_type=configured_trigger_type,
                    run_trigger_type=run_trigger_type,
                    run_trigger_source=";".join(trigger_source_parts),
                    marketplace_id=marketplace_id,
                    profile_id=profile_id,
                    artifact_scope=artifact_scope,
                    window=audit_window,
                    command_line_hash=command_line_hash(
                        ["scripts/run_automation_stage.py", *vars(args)]
                    ),
                    config_snapshot_json=build_config_snapshot(
                        workflow=args.workflow,
                        phase=args.phase,
                        reference_date=reference_date,
                        week_start=week_start,
                        month=args.month,
                        send_email=args.send_email,
                        force_resend=args.force_resend,
                        continue_on_error=args.continue_on_error,
                        skip_artifact_store=args.skip_artifact_store,
                        email_to=_split_email_values(args.email_to),
                    ),
                    started_at=started_at,
                )
            )
    else:
        connection_ctx = None

    restored_count = 0
    saved_count = 0
    skipped_count = 0
    commands_total = len(commands)
    commands_failed = 0
    final_status = "running"
    final_error: BaseException | None = None

    try:
        if artifact_service and args.phase != "submit":
            restore = artifact_service.restore_scope(
                artifact_scope=artifact_scope,
                output_root=".",
                path_prefixes=_RESTORE_PREFIXES,
                dry_run=not args.execute,
            )
            restored_count = restore.restored_count
            if audit_service:
                audit_service.link_restored_artifacts(restore)
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
            command_started=(
                audit_service.command_started if audit_service is not None else None
            ),
            command_finished=(
                audit_service.command_finished if audit_service is not None else None
            ),
        )

        print(
            f"Automation stage workflow={result.workflow} phase={result.phase} "
            f"mode={'execute' if result.executed else 'dry_run'} scope={result.artifact_scope} "
            f"commands={len(result.commands)} failed={result.failed_count}"
        )
        commands_failed = result.failed_count
        for index, command in enumerate(result.commands, start=1):
            code_suffix = ""
            if result.executed and index <= len(result.return_codes):
                code_suffix = f" exit_code={result.return_codes[index - 1]}"
            print(f"{index}. {command.label}: {command.printable()}{code_suffix}")

        if result.executed and result.failed_count:
            final_status = "failed"
        else:
            final_status = "succeeded"

        if audit_service:
            audit_service.write_stage_result_artifact(
                path=_stage_result_path(artifact_scope=artifact_scope, phase=args.phase),
                status=final_status,
                workflow=args.workflow,
                phase=args.phase,
                artifact_scope=artifact_scope,
                started_at=started_at,
                finished_at=datetime.now(tz=UTC),
                commands_total=len(result.commands),
                commands_failed=result.failed_count,
                artifact_restored_count=restored_count,
                artifact_saved_count=0,
                artifact_skipped_count=0,
            )

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
            saved_count = save.saved_count
            skipped_count = save.skipped_count
            if audit_service:
                audit_service.link_saved_artifacts(save)
                audit_service.insert_table_write_summaries_from_saved_artifacts(
                    save_result=save, root="."
                )
            print(
                f"artifact_save scope={artifact_scope} "
                f"mode={'execute' if args.execute else 'dry_run'} scanned={save.scanned_count} "
                f"saved={save.saved_count} skipped={save.skipped_count}"
            )
        if result.executed and result.failed_count:
            raise SystemExit(1)
    except BaseException as exc:
        final_error = exc
        final_status = "failed" if not isinstance(exc, SystemExit) else final_status or "failed"
        raise
    finally:
        finished_at = datetime.now(tz=UTC)
        if audit_service:
            if final_error is not None and final_status == "running":
                final_status = "failed"
            audit_service.finish_run(
                status=final_status if final_status != "running" else "failed",
                finished_at=finished_at,
                started_at=started_at,
                commands_total=commands_total,
                commands_failed=commands_failed,
                artifact_restored_count=restored_count,
                artifact_saved_count=saved_count,
                artifact_skipped_count=skipped_count,
                error=final_error,
            )
        if connection_ctx is not None:
            connection_ctx.__exit__(None, None, None)


def _stage_result_path(*, artifact_scope: str, phase: str) -> Path:
    safe_scope = artifact_scope.replace(":", "_").replace("/", "_")
    return Path("runtime/automation_audit") / safe_scope / phase / "stage_result.json"


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
