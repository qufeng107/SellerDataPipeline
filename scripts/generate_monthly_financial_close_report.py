from __future__ import annotations

import argparse
import json
from pathlib import Path

from seller_data_pipeline.common.cli import run_cli_main
from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.db.connection import get_connection
from seller_data_pipeline.db.repositories.monthly_financial_close_repo import (
    MonthlyFinancialCloseRepo,
)
from seller_data_pipeline.services.monthly_financial_close_service import (
    DEFAULT_OUTPUT_ROOT,
    MonthlyFinancialCloseService,
    month_to_date_range,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a read-only Monthly Financial Close Report from normalized Azure SQL "
            "tables. v1 writes JSON + one XLSX workbook and does not write report result tables."
        )
    )
    parser.add_argument(
        "--marketplace-id",
        default=None,
        help="Amazon marketplace ID, for example ATVPDKIKX0DER. Defaults to .env.",
    )
    parser.add_argument(
        "--profile-id",
        default=None,
        help=(
            "Amazon Ads profile ID for Ads API operational context. Defaults to "
            "AMAZON_ADS_PROFILE_ID when available."
        ),
    )
    parser.add_argument(
        "--month",
        required=True,
        help="Natural calendar month in YYYY-MM format, for example 2026-03.",
    )
    parser.add_argument(
        "--output-root",
        default=DEFAULT_OUTPUT_ROOT,
        help=(
            "Output root. Defaults to "
            "runtime/analysis_reports/monthly_financial_close."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Compatibility/safety flag. The report is always read-only against the database; "
            "dry-run still writes JSON/XLSX files for manual review."
        ),
    )
    parser.add_argument(
        "--json-output",
        default=None,
        help="Optional extra JSON path for CI/local automation summaries.",
    )
    parser.add_argument(
        "--fail-on-review",
        action="store_true",
        help="Exit non-zero when report status is needs_review or no_data.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    marketplace_id = args.marketplace_id or settings.amazon_marketplace_id
    if not marketplace_id:
        raise SystemExit("Missing --marketplace-id or AMAZON_MARKETPLACE_ID.")
    profile_id = args.profile_id or settings.amazon_ads_profile_id
    start_date, end_date = month_to_date_range(args.month)

    with get_connection(settings=settings, autocommit=True) as connection:
        service = MonthlyFinancialCloseService(repo=MonthlyFinancialCloseRepo(connection))
        result = service.run(
            marketplace_id=marketplace_id,
            profile_id=profile_id,
            month=args.month,
            output_root=args.output_root,
        )

    payload = result.to_dict()
    if args.json_output:
        output_path = Path(args.json_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print(f"Monthly Financial Close status={result.status} dry_run={args.dry_run}")
    print(
        "period={start}..{end} month={month} marketplace={marketplace} "
        "profile={profile} settlement_rows={rows} settlement_net={net} "
        "internal_cogs={cogs} estimated_profit={profit}".format(
            start=start_date.isoformat(),
            end=end_date.isoformat(),
            month=args.month,
            marketplace=marketplace_id,
            profile=profile_id or "-",
            rows=result.settlement_row_count,
            net=result.financial_summary.settlement_net_amount,
            cogs=result.financial_summary.internal_cogs,
            profit=result.financial_summary.estimated_operating_profit,
        )
    )
    reconciliation_warnings = [
        check for check in result.reconciliation_checks if check.status == "warning"
    ]
    reconciliation_needs_review = [
        check for check in result.reconciliation_checks if check.status == "needs_review"
    ]
    non_info_warnings = [
        warning for warning in result.warnings if warning.severity != "info"
    ]
    print(
        "reconciliation_warnings={warnings} reconciliation_needs_review={needs_review} "
        "non_info_warnings={non_info}".format(
            warnings=len(reconciliation_warnings),
            needs_review=len(reconciliation_needs_review),
            non_info=len(non_info_warnings),
        )
    )
    for name, path in result.output_files.items():
        print(f"{name}={path}")
    non_ok_checks = [
        check for check in result.reconciliation_checks if check.status != "ok"
    ]
    if non_ok_checks:
        print("reconciliation_non_ok_checks:")
        for check in non_ok_checks:
            print(
                "- [{severity}] {name}: expected={expected} actual={actual} "
                "diff={diff} message={message}".format(
                    severity=check.severity,
                    name=check.check_name,
                    expected=check.expected,
                    actual=check.actual,
                    diff=check.diff,
                    message=check.message,
                )
            )
    if result.warnings:
        print("warnings:")
        for warning in result.warnings:
            print(f"- [{warning.severity}] {warning.warning_code}: {warning.message}")
    if args.fail_on_review and result.status != "ok":
        raise SystemExit(2)


if __name__ == "__main__":
    run_cli_main(main)
