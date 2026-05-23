from __future__ import annotations

import argparse

from seller_data_pipeline.common.cli import run_cli_main
from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.services.manual_refresh_plan_service import ManualRefreshPlanService


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run a standard manual refresh plan. Submit/ingest phases only print commands "
            "unless --execute is passed. Collect and audit are read-only but also follow the "
            "same --execute safety rule for consistency."
        )
    )
    parser.add_argument(
        "--plan",
        choices=["core_rolling", "weekly_full"],
        required=True,
        help="core_rolling for every 1-2 days; weekly_full for weekly complete refresh.",
    )
    parser.add_argument(
        "--phase",
        choices=["submit", "collect", "ingest", "audit"],
        required=True,
        help="Plan phase to run.",
    )
    parser.add_argument(
        "--marketplace-id",
        default=None,
        help="Marketplace ID. Defaults to AMAZON_MARKETPLACE_ID.",
    )
    parser.add_argument(
        "--profile-id",
        default=None,
        help="Amazon Ads profile ID. Defaults to AMAZON_ADS_PROFILE_ID where needed.",
    )
    parser.add_argument(
        "--target-start-date",
        default="2026-03-01",
        help="Coverage audit target start date. Default: 2026-03-01.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually run the planned commands. Default only prints the command list.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reserved for future plan variants; current fixed rolling commands already force where needed.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue remaining commands even if one command exits non-zero.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    marketplace_id = args.marketplace_id or settings.amazon_marketplace_id
    if not marketplace_id:
        raise SystemExit("Missing --marketplace-id or AMAZON_MARKETPLACE_ID.")
    profile_id = args.profile_id or settings.amazon_ads_profile_id

    result = ManualRefreshPlanService().run(
        plan=args.plan,
        phase=args.phase,
        marketplace_id=marketplace_id,
        profile_id=profile_id,
        target_start_date=args.target_start_date,
        execute=args.execute,
        force=args.force,
        stop_on_error=not args.continue_on_error,
    )

    print(
        f"Manual refresh plan={result.plan} phase={result.phase} "
        f"mode={'execute' if result.executed else 'dry_run'} commands={len(result.commands)}"
    )
    for index, command in enumerate(result.commands, start=1):
        code_suffix = ""
        if result.executed and index <= len(result.return_codes):
            code_suffix = f" exit_code={result.return_codes[index - 1]}"
        print(f"{index}. {command.label}: {command.printable()}{code_suffix}")
    if not result.executed:
        print("Dry-run only. Re-run with --execute to run these commands.")
    elif result.failed_count:
        raise SystemExit(1)


if __name__ == "__main__":
    run_cli_main(main)
