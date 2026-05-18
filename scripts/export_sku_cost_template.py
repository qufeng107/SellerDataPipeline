from __future__ import annotations

import argparse
from pathlib import Path

from seller_data_pipeline.common.cli import run_cli_main
from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.db.connection import get_connection
from seller_data_pipeline.db.repositories.sku_cost_repo import SkuCostRepo
from seller_data_pipeline.services.sku_cost_service import DEFAULT_CURRENCY, SkuCostWorkbookService


def build_default_output_path(*, marketplace_id: str) -> Path:
    return Path("runtime") / "sku_cost_templates" / marketplace_id / "sku_cost_template.xlsx"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export an idempotent Excel template for manual SKU standard cost input. "
            "The generated xlsx is a working file; only filled new_* columns are imported."
        ),
    )
    parser.add_argument(
        "--marketplace-id",
        default=None,
        help="Amazon marketplace ID, for example ATVPDKIKX0DER. Defaults to .env.",
    )
    parser.add_argument(
        "--output-path",
        default=None,
        help=(
            "Output xlsx path. Defaults to "
            "runtime/sku_cost_templates/{marketplace_id}/sku_cost_template.xlsx."
        ),
    )
    parser.add_argument(
        "--currency",
        default=DEFAULT_CURRENCY,
        help="Default currency prefilled in new_currency. Defaults to USD.",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Do not delete an existing output xlsx before export. Default is idempotent replace.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    marketplace_id = args.marketplace_id or settings.amazon_marketplace_id
    if not marketplace_id:
        raise SystemExit("Missing --marketplace-id or AMAZON_MARKETPLACE_ID.")

    output_path = Path(args.output_path) if args.output_path else build_default_output_path(
        marketplace_id=marketplace_id
    )
    service = SkuCostWorkbookService()
    with get_connection(settings=settings) as connection:
        result = service.export_template(
            repo=SkuCostRepo(connection),
            marketplace_id=marketplace_id,
            output_path=output_path,
            currency=args.currency,
            delete_existing=not args.keep_existing,
        )

    print("SKU cost template exported.")
    print(f"marketplace={result.marketplace_id}")
    print(f"rows={result.row_count}")
    print(f"generated_at_utc={result.generated_at_utc.isoformat()}")
    print(f"xlsx={result.output_path}")


if __name__ == "__main__":
    run_cli_main(main)
