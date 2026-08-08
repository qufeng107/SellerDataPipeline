from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from seller_data_pipeline.common.cli import run_cli_main
from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.ingestion.orders_ingestion import OrdersIngestionService
from seller_data_pipeline.ingestion.period_raw_file_selection import select_sp_api_period_raw_files


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run guarded SP-API All Orders ingestion. The default mode is dry-run only; "
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
            "Optional explicit GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL raw file. "
            "If omitted, the latest file under reports/raw/amazon/{marketplace}/... is used."
        ),
    )
    parser.add_argument("--start-date", default=None, help="Optional period start YYYY-MM-DD; requires --end-date.")
    parser.add_argument("--end-date", default=None, help="Optional period end YYYY-MM-DD; requires --start-date.")
    parser.add_argument(
        "--output-root",
        default="runtime/ingestion/sp_api",
        help="Root directory for preview rows and audit manifests.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually connect to Azure SQL and upsert rows. Without this flag, no DB writes occur.",
    )
    parser.add_argument(
        "--allow-review",
        action="store_true",
        help=(
            "Do not exit non-zero when schema/privacy review is required. Database writes are still "
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

    service = OrdersIngestionService(
        raw_reports_root=settings.raw_reports_root,
        output_root=args.output_root,
    )
    if bool(args.start_date) != bool(args.end_date):
        raise SystemExit("--start-date and --end-date must be provided together.")
    if args.raw_file and args.start_date:
        raise SystemExit("Use either --raw-file or --start-date/--end-date, not both.")

    results = []
    if args.start_date:
        start_date = date.fromisoformat(args.start_date)
        end_date = date.fromisoformat(args.end_date)
        selection = select_sp_api_period_raw_files(
            sampling_root=settings.local_sampling_root,
            marketplace_id=marketplace_id,
            report_type="GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL",
            start_date=start_date,
            end_date=end_date,
        )
        missing = ",".join(f"{a}..{b}" for a, b in selection.missing_ranges) or "none"
        print(
            f"period_file_selection report_type={selection.report_type} "
            f"files_selected={selection.selected_file_count} "
            f"coverage_complete={selection.coverage_complete} missing_ranges={missing}"
        )
        if not selection.coverage_complete:
            raise SystemExit(2)
        for index, item in enumerate(selection.files, start=1):
            print(
                f"period_file[{index}/{selection.selected_file_count}] "
                f"report_id={item.report_id} range={item.start_date}..{item.end_date}"
            )
            results.append(
                service.run(
                    marketplace_id=marketplace_id,
                    raw_file_path=item.raw_file_path,
                    execute=args.execute,
                    fail_on_review=not args.allow_review,
                )
            )
    else:
        results.append(
            service.run(
                marketplace_id=marketplace_id,
                raw_file_path=args.raw_file,
                execute=args.execute,
                fail_on_review=not args.allow_review,
            )
        )

    result = results[-1]
    payload = result.to_dict() if len(results) == 1 else {
        "workflow_name": "sp_api_orders_period_ingestion",
        "result_count": len(results),
        "results": [item.to_dict() for item in results],
    }
    if args.json_output:
        output_path = Path(args.json_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    total_prepared = sum(item.dry_run_result.prepared_row_count for item in results)
    total_attempted = sum(item.upsert_result.attempted_rows for item in results if item.upsert_result)
    total_inserted = sum(item.upsert_result.inserted_rows for item in results if item.upsert_result)
    total_updated = sum(item.upsert_result.updated_rows for item in results if item.upsert_result)
    total_written = sum(item.upsert_result.written_rows for item in results if item.upsert_result)
    total_skipped = sum(item.upsert_result.skipped_rows for item in results if item.upsert_result)
    failed = sum(1 for item in results if item.requires_review or item.status not in {"success", "dry_run_success"})
    print(
        f"Orders period ingestion files_processed={len(results)} failed={failed} "
        f"prepared_rows={total_prepared} attempted={total_attempted} inserted={total_inserted} "
        f"updated={total_updated} written={total_written} skipped={total_skipped}"
    )
    for item in results:
        print(f"Orders ingestion mode={item.mode} status={item.status}")
        print(item.message)
        print(f"dry_run_output_dir={item.dry_run_result.output_dir}")
        print(
            f"prepared_rows={item.dry_run_result.prepared_row_count} requires_review={item.requires_review} sync_run_id={item.sync_run_id}"
        )
    if failed and not args.allow_review:
        raise SystemExit(2)



if __name__ == "__main__":
    run_cli_main(main)
