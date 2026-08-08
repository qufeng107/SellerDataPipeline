from __future__ import annotations

import argparse
import json

from seller_data_pipeline.common.cli import run_cli_main
from seller_data_pipeline.ingestion.settlement_idempotency_repair import (
    SettlementIdempotencyRepairService,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit or repair exact duplicate Settlement source identities. "
            "Dry-run is the default; pass --execute to delete exact duplicates."
        )
    )
    parser.add_argument("--marketplace-id", default=None)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = SettlementIdempotencyRepairService().run(
        marketplace_id=args.marketplace_id,
        execute=args.execute,
    )
    if args.as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str))
    else:
        print(
            "Settlement idempotency repair "
            f"mode={result.mode} status={result.status} "
            f"duplicate_groups={result.duplicate_group_count} "
            f"repairable={result.repairable_group_count} "
            f"conflicts={result.conflict_group_count} "
            f"rows_to_delete={result.rows_to_delete} rows_deleted={result.rows_deleted}"
        )
        for plan in result.plans:
            identity = plan.identity
            print(
                f"- status={plan.status} marketplace={identity.marketplace_id} "
                f"report_id={identity.source_report_id} row_index={identity.source_row_index} "
                f"duplicates={identity.duplicate_count} keep={plan.keep_row_id} "
                f"delete={list(plan.delete_row_ids)} message={plan.message}"
            )
    if result.requires_review:
        raise SystemExit(2)


if __name__ == "__main__":
    run_cli_main(main)
