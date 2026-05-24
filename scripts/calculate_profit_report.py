from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from seller_data_pipeline.common.cli import run_cli_main
from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.db.connection import get_connection
from seller_data_pipeline.db.repositories.finance_repo import FinanceRepo
from seller_data_pipeline.services.calculate_profit_service import CalculateProfitService


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a read-only Settlement-led profit preview from normalized Azure SQL "
            "tables. This does not write profit result tables."
        )
    )
    parser.add_argument(
        "--marketplace-id",
        default=None,
        help="Amazon marketplace ID, for example ATVPDKIKX0DER. Defaults to .env.",
    )
    parser.add_argument(
        "--period",
        default="custom",
        choices=("custom", "weekly", "monthly"),
        help="Optional period label for logs/output review. Dates are still explicit.",
    )
    parser.add_argument("--start-date", required=True, help="Inclusive period start, YYYY-MM-DD.")
    parser.add_argument("--end-date", required=True, help="Inclusive period end, YYYY-MM-DD.")
    parser.add_argument(
        "--output-root",
        default="runtime/profit_reports",
        help="Output root for preview JSON/Markdown/CSV files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compatibility flag. Profit v1 is always read-only and writes preview files only.",
    )
    parser.add_argument(
        "--json-output",
        default=None,
        help="Optional extra JSON path for CI/local automation summaries.",
    )
    parser.add_argument(
        "--fail-on-review",
        action="store_true",
        help="Exit non-zero when the preview status is needs_review or no_data.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    marketplace_id = args.marketplace_id or settings.amazon_marketplace_id
    if not marketplace_id:
        raise SystemExit("Missing --marketplace-id or AMAZON_MARKETPLACE_ID.")

    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date)

    with get_connection(settings=settings, autocommit=True) as connection:
        service = CalculateProfitService(repo=FinanceRepo(connection))
        result = service.run(
            marketplace_id=marketplace_id,
            start_date=start_date,
            end_date=end_date,
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

    print(f"Profit preview status={result.status} period={args.period} dry_run={args.dry_run}")
    print(
        f"period={result.start_date.isoformat()}..{result.end_date.isoformat()} marketplace={result.marketplace_id} settlement_rows={result.settlement_row_count} "
        f"settlement_net={result.settlement_net_amount} internal_cogs={result.internal_cogs} estimated_profit={result.estimated_operating_profit}"
    )
    for name, path in result.output_files.items():
        print(f"{name}={path}")
    if result.warnings:
        print("warnings:")
        for warning in result.warnings:
            print(f"- {warning}")
    if args.fail_on_review and result.status != "ok":
        raise SystemExit(2)


if __name__ == "__main__":
    run_cli_main(main)
