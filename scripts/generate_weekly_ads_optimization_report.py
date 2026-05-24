from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path

from seller_data_pipeline.common.cli import run_cli_main
from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.db.connection import get_connection
from seller_data_pipeline.db.repositories.weekly_ads_optimization_repo import (
    WeeklyAdsOptimizationRepo,
)
from seller_data_pipeline.services.weekly_ads_optimization_service import (
    DEFAULT_OUTPUT_ROOT,
    WeeklyAdsOptimizationService,
    WeeklyAdsOptimizationThresholds,
    parse_week_start,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a read-only Weekly Ads Optimization Report from normalized Azure "
            "SQL Ads tables. v1 writes JSON + one XLSX workbook and does not call Ads "
            "write APIs."
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
        help=("Amazon Ads profile ID. Defaults to AMAZON_ADS_PROFILE_ID when available."),
    )
    parser.add_argument(
        "--week-start",
        required=True,
        help="7-day report period start in YYYY-MM-DD format. Scheduled reports use Saturday starts.",
    )
    parser.add_argument(
        "--output-root",
        default=DEFAULT_OUTPUT_ROOT,
        help="Output root. Defaults to runtime/analysis_reports/weekly_ads_optimization.",
    )
    parser.add_argument("--target-acos", default="0.30", help="Default: 0.30.")
    parser.add_argument("--watch-acos", default="0.40", help="Default: 0.40.")
    parser.add_argument("--target-tacos", default="0.20", help="Default: 0.20.")
    parser.add_argument("--no-sale-cost-threshold", default="10.00", help="Default: 10.00.")
    parser.add_argument(
        "--no-order-click-threshold",
        type=int,
        default=12,
        help="Default: 12 clicks.",
    )
    parser.add_argument(
        "--min-purchases-to-scale",
        type=int,
        default=2,
        help="Default: 2 attributed purchases.",
    )
    parser.add_argument("--min-sales-to-scale", default="40.00", help="Default: 40.00.")
    parser.add_argument("--low-ctr-threshold", default="0.002", help="Default: 0.002.")
    parser.add_argument("--low-cvr-threshold", default="0.03", help="Default: 0.03.")
    parser.add_argument("--high-cpc-multiplier", default="1.5", help="Default: 1.5.")
    parser.add_argument(
        "--stable-lag-days",
        type=int,
        default=3,
        help="Ads attribution stable lag days. Default: 3.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Compatibility/safety flag. The report is always read-only against the "
            "database; dry-run still writes JSON/XLSX files for manual review."
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
        help="Exit non-zero when report status is needs_backfill or no_ads_data.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    marketplace_id = args.marketplace_id or settings.amazon_marketplace_id
    if not marketplace_id:
        raise SystemExit("Missing --marketplace-id or AMAZON_MARKETPLACE_ID.")
    profile_id = args.profile_id or settings.amazon_ads_profile_id
    if not profile_id:
        raise SystemExit("Missing --profile-id or AMAZON_ADS_PROFILE_ID.")
    week_start = parse_week_start(args.week_start)
    thresholds = WeeklyAdsOptimizationThresholds(
        target_acos=Decimal(args.target_acos),
        watch_acos=Decimal(args.watch_acos),
        target_tacos=Decimal(args.target_tacos),
        no_sale_cost_threshold=Decimal(args.no_sale_cost_threshold),
        no_order_click_threshold=args.no_order_click_threshold,
        min_purchases_to_scale=args.min_purchases_to_scale,
        min_sales_to_scale=Decimal(args.min_sales_to_scale),
        low_ctr_threshold=Decimal(args.low_ctr_threshold),
        low_cvr_threshold=Decimal(args.low_cvr_threshold),
        high_cpc_multiplier=Decimal(args.high_cpc_multiplier),
        stable_lag_days=args.stable_lag_days,
    )

    with get_connection(settings=settings, autocommit=True) as connection:
        service = WeeklyAdsOptimizationService(repo=WeeklyAdsOptimizationRepo(connection))
        result = service.run(
            marketplace_id=marketplace_id,
            profile_id=profile_id,
            week_start=week_start,
            output_root=args.output_root,
            thresholds=thresholds,
        )

    payload = result.to_dict()
    if args.json_output:
        output_path = Path(args.json_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    overall = result.overall_summary
    print(f"Weekly Ads Optimization status={result.status} dry_run={args.dry_run}")
    print(
        f"period={result.week_start.isoformat()}..{result.week_end.isoformat()} marketplace={marketplace_id} profile={profile_id} "
        f"ads_spend={overall.ads_spend} ads_sales_7d={overall.ads_sales_7d} purchases={overall.ads_purchases_7d} "
        f"clicks={overall.clicks} acos={_display_ratio(overall.acos)} tacos={_display_ratio(overall.tacos)} action_items={len(result.action_items)}"
    )
    reconciliation_warnings = [
        check for check in result.reconciliation_checks if check.status == "warning"
    ]
    reconciliation_needs_review = [
        check for check in result.reconciliation_checks if check.status == "needs_review"
    ]
    non_info_warnings = [warning for warning in result.warnings if warning.severity != "info"]
    print(
        f"reconciliation_warnings={len(reconciliation_warnings)} reconciliation_needs_review={len(reconciliation_needs_review)} "
        f"non_info_warnings={len(non_info_warnings)} search_term_actions={len(result.search_term_action_candidates)}"
    )
    for name, path in result.output_files.items():
        print(f"{name}={path}")
    non_ok_checks = [check for check in result.reconciliation_checks if check.status != "ok"]
    if non_ok_checks:
        print("reconciliation_non_ok_checks:")
        for check in non_ok_checks:
            print(
                f"- [{check.severity}] {check.check_name}: expected={check.expected} actual={check.actual} "
                f"message={check.message}"
            )
    if result.warnings:
        print("warnings:")
        for warning in result.warnings:
            print(f"- [{warning.severity}] {warning.warning_code}: {warning.message}")
    if args.fail_on_review and result.status in {"needs_backfill", "no_ads_data"}:
        raise SystemExit(2)


def _display_ratio(value: Decimal | None) -> str:
    if value is None:
        return "-"
    return f"{(value * Decimal('100')).quantize(Decimal('0.01'))}%"


if __name__ == "__main__":
    run_cli_main(main)
