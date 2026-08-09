from __future__ import annotations

import argparse
import json

from seller_data_pipeline.common.cli import run_cli_main
from seller_data_pipeline.ingestion.settlement_marketplace_integrity_repair import (
    SettlementMarketplaceIntegrityRepairService,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit or remove Settlement source reports whose currency conflicts with the "
            "verified marketplace currency. Dry-run is the default; pass --execute only "
            "after reviewing the plan."
        )
    )
    parser.add_argument("--marketplace-id", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--include-plans", action="store_true")
    parser.add_argument("--plan-sample-limit", type=int, default=20)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.plan_sample_limit < 0:
        raise SystemExit("--plan-sample-limit must be >= 0")

    result = SettlementMarketplaceIntegrityRepairService().run(
        marketplace_id=args.marketplace_id,
        execute=args.execute,
    )
    if args.as_json:
        payload = (
            result.to_dict()
            if args.include_plans
            else result.to_summary_dict(sample_limit=args.plan_sample_limit)
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        print(
            "Settlement marketplace integrity repair "
            f"mode={result.mode} status={result.status} "
            f"marketplace={result.marketplace_id} expected_currency={result.expected_currency} "
            f"scanned_rows={result.scanned_row_count} "
            f"mismatched_reports={result.mismatched_report_count} "
            f"repairable={result.repairable_report_count} "
            f"conflicts={result.conflict_report_count} "
            f"rows_to_delete={result.rows_to_delete} rows_deleted={result.rows_deleted}"
        )
        if args.include_plans:
            for plan in result.plans:
                print(
                    f"- status={plan.status} report_id={plan.source_report_id} "
                    f"currencies={list(plan.observed_currencies)} rows={plan.row_count} "
                    f"amount_total={plan.amount_total} paths={list(plan.raw_file_paths)} "
                    f"message={plan.message}"
                )
    if result.requires_review:
        raise SystemExit(2)


if __name__ == "__main__":
    run_cli_main(main)
