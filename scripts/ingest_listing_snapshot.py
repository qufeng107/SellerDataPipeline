from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from seller_data_pipeline.common.cli import run_cli_main
from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.ingestion.listing_ingestion import ListingIngestionService


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run guarded SP-API Listing snapshot ingestion. The default mode is dry-run only; "
            "use --execute to write to Azure SQL after migrations have been applied."
        )
    )
    parser.add_argument(
        "--marketplace-id",
        default=None,
        help="Amazon marketplace ID, for example ATVPDKIKX0DER. Defaults to .env.",
    )
    parser.add_argument(
        "--raw-file",
        default=None,
        help=(
            "Optional explicit GET_MERCHANT_LISTINGS_ALL_DATA raw file. "
            "If omitted, the latest file under reports/raw/amazon/{marketplace}/... is used."
        ),
    )
    parser.add_argument(
        "--snapshot-date",
        default=None,
        help="Snapshot date in YYYY-MM-DD. Defaults to raw-file date directory or today.",
    )
    parser.add_argument(
        "--currency",
        default="USD",
        help="Currency stamped on listing prices. Defaults to USD for US marketplace canary.",
    )
    parser.add_argument(
        "--output-root",
        default="runtime/ingestion/sp_api",
        help="Root directory for preview rows and audit manifests.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Actually connect to Azure SQL and upsert rows. Without this flag, no DB writes occur."
        ),
    )
    parser.add_argument(
        "--allow-review",
        action="store_true",
        help=(
            "Do not exit non-zero when schema review is required. Database writes are still "
            "blocked when review is required."
        ),
    )
    parser.add_argument(
        "--json-output",
        default=None,
        help="Optional path to write the ingestion run result JSON.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    marketplace_id = args.marketplace_id or settings.amazon_marketplace_id
    if not marketplace_id:
        raise SystemExit("Missing --marketplace-id or AMAZON_MARKETPLACE_ID.")

    snapshot_date = date.fromisoformat(args.snapshot_date) if args.snapshot_date else None
    service = ListingIngestionService(
        raw_reports_root=settings.raw_reports_root,
        output_root=args.output_root,
    )
    result = service.run(
        marketplace_id=marketplace_id,
        raw_file_path=args.raw_file,
        snapshot_date=snapshot_date,
        currency=args.currency,
        execute=args.execute,
        fail_on_review=not args.allow_review,
    )
    payload = result.to_dict()
    if args.json_output:
        output_path = Path(args.json_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print(f"Listing ingestion mode={result.mode} status={result.status}")
    print(result.message)
    print(f"dry_run_output_dir={result.dry_run_result.output_dir}")
    print(
        f"prepared_rows={result.dry_run_result.prepared_row_count} requires_review={result.requires_review} sync_run_id={result.sync_run_id}"
    )
    if result.upsert_result is not None:
        table_result = result.upsert_result.table_result
        print(
            f"upsert attempted={result.upsert_result.attempted_rows} inserted={result.upsert_result.inserted_rows} updated={result.upsert_result.updated_rows} "
            f"written={result.upsert_result.written_rows} skipped={result.upsert_result.skipped_rows}"
        )
        print(
            f"{table_result.table_name}: attempted={table_result.attempted_rows} inserted={table_result.inserted_rows} updated={table_result.updated_rows} skipped={table_result.skipped_rows}"
        )
    if result.requires_review and not args.allow_review:
        raise SystemExit(2)


if __name__ == "__main__":
    run_cli_main(main)
