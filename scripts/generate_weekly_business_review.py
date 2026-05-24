from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path

from seller_data_pipeline.common.cli import run_cli_main
from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.db.connection import get_connection
from seller_data_pipeline.db.repositories.weekly_business_review_repo import (
    WeeklyBusinessReviewRepo,
)
from seller_data_pipeline.services.weekly_business_review_service import (
    DEFAULT_OUTPUT_ROOT,
    WeeklyBusinessReviewService,
    parse_week_start,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a read-only Weekly Business Review from normalized Azure SQL tables. "
            "v1 writes JSON + one XLSX workbook and does not write report result tables."
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
        "--week-start",
        required=True,
        help="7-day report period start in YYYY-MM-DD format. Scheduled reports use Saturday starts.",
    )
    parser.add_argument(
        "--output-root",
        default=DEFAULT_OUTPUT_ROOT,
        help="Output root. Defaults to runtime/analysis_reports/weekly_business_review.",
    )
    parser.add_argument(
        "--target-acos",
        default="0.30",
        help="Target ACOS warning threshold as decimal. Default: 0.30.",
    )
    parser.add_argument(
        "--target-tacos",
        default="0.20",
        help="Target TACOS warning threshold as decimal. Default: 0.20.",
    )
    parser.add_argument(
        "--low-stock-days",
        type=int,
        default=14,
        help="Urgent low-stock days-of-supply threshold. Default: 14.",
    )
    parser.add_argument(
        "--watch-stock-days",
        type=int,
        default=30,
        help="Watch low-stock days-of-supply threshold. Default: 30.",
    )
    parser.add_argument(
        "--min-stable-lag-days",
        type=int,
        default=2,
        help="Sales/Orders stable lag days. Default: 2.",
    )
    parser.add_argument(
        "--ads-stable-lag-days",
        type=int,
        default=3,
        help="Ads stable lag days. Default: 3.",
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
    week_start = parse_week_start(args.week_start)

    with get_connection(settings=settings, autocommit=True) as connection:
        service = WeeklyBusinessReviewService(repo=WeeklyBusinessReviewRepo(connection))
        result = service.run(
            marketplace_id=marketplace_id,
            profile_id=profile_id,
            week_start=week_start,
            output_root=args.output_root,
            target_acos=Decimal(args.target_acos),
            target_tacos=Decimal(args.target_tacos),
            low_stock_days=args.low_stock_days,
            watch_stock_days=args.watch_stock_days,
            min_stable_lag_days=args.min_stable_lag_days,
            ads_stable_lag_days=args.ads_stable_lag_days,
        )

    payload = result.to_dict()
    if args.json_output:
        output_path = Path(args.json_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print(f"Weekly Business Review status={result.status} dry_run={args.dry_run}")
    print(
        "period={start}..{end} marketplace={marketplace} profile={profile} "
        "sales={sales} units={units} sessions={sessions} ads_spend={ads_spend} "
        "estimated_cogs={cogs} contribution_after_ads={contribution}".format(
            start=result.week_start.isoformat(),
            end=result.week_end.isoformat(),
            marketplace=marketplace_id,
            profile=profile_id or "-",
            sales=result.sales_traffic_summary.ordered_product_sales,
            units=result.sales_traffic_summary.units_ordered,
            sessions=result.sales_traffic_summary.sessions,
            ads_spend=result.ads_summary.spend,
            cogs=result.estimated_cogs,
            contribution=result.contribution_after_ads,
        )
    )
    reconciliation_warnings = [
        check for check in result.reconciliation_checks if check.status == "warning"
    ]
    reconciliation_needs_review = [
        check for check in result.reconciliation_checks if check.status == "needs_review"
    ]
    non_info_warnings = [warning for warning in result.warnings if warning.severity != "info"]
    print(
        "reconciliation_warnings={warnings} reconciliation_needs_review={needs_review} "
        "non_info_warnings={non_info} alerts={alerts}".format(
            warnings=len(reconciliation_warnings),
            needs_review=len(reconciliation_needs_review),
            non_info=len(non_info_warnings),
            alerts=len(result.alerts),
        )
    )
    for name, path in result.output_files.items():
        print(f"{name}={path}")
    non_ok_checks = [check for check in result.reconciliation_checks if check.status != "ok"]
    if non_ok_checks:
        print("reconciliation_non_ok_checks:")
        for check in non_ok_checks:
            print(
                "- [{severity}] {name}: expected={expected} actual={actual} "
                "message={message}".format(
                    severity=check.severity,
                    name=check.check_name,
                    expected=check.expected,
                    actual=check.actual,
                    message=check.message,
                )
            )
    if result.warnings:
        print("warnings:")
        for warning in result.warnings:
            print(f"- [{warning.severity}] {warning.warning_code}: {warning.message}")
    if args.fail_on_review and result.status in {"needs_review", "no_data"}:
        raise SystemExit(2)


if __name__ == "__main__":
    run_cli_main(main)
