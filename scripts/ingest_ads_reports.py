from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from seller_data_pipeline.common.cli import run_cli_main
from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.ingestion.ads_ingestion import AdsIngestionService
from seller_data_pipeline.ingestion.ads_table_mapping import ADS_TARGET_TABLE_SPECS
from seller_data_pipeline.ingestion.period_raw_file_selection import select_ads_period_raw_files


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run guarded Amazon Ads ingestion. The default mode is dry-run only; "
            "use --execute to write to Azure SQL after migrations have been applied."
        )
    )
    parser.add_argument(
        "--profile-id",
        default=None,
        help="Amazon Ads profile ID. Defaults to AMAZON_ADS_PROFILE_ID from .env.",
    )
    parser.add_argument(
        "--marketplace-id",
        default=None,
        help="Amazon marketplace ID to stamp on rows, for example ATVPDKIKX0DER.",
    )
    parser.add_argument(
        "--report-type-id",
        action="append",
        default=None,
        help="Ads reportTypeId to ingest. Repeat for multiple report types.",
    )
    parser.add_argument("--start-date", default=None, help="Optional period start YYYY-MM-DD; requires --end-date.")
    parser.add_argument("--end-date", default=None, help="Optional period end YYYY-MM-DD; requires --start-date.")
    parser.add_argument(
        "--output-root",
        default="runtime/ingestion/amazon_ads",
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
    profile_id = args.profile_id or settings.amazon_ads_profile_id
    if not profile_id:
        raise SystemExit("Missing --profile-id or AMAZON_ADS_PROFILE_ID.")

    if bool(args.start_date) != bool(args.end_date):
        raise SystemExit("--start-date and --end-date must be provided together.")

    raw_file_paths_by_report_type = None
    report_type_ids = args.report_type_id
    if args.start_date:
        start_date = date.fromisoformat(args.start_date)
        end_date = date.fromisoformat(args.end_date)
        report_type_ids = report_type_ids or [
            spec.report_type_id for spec in ADS_TARGET_TABLE_SPECS if spec.table_ready
        ]
        raw_file_paths_by_report_type = {}
        incomplete = False
        for report_type_id in report_type_ids:
            selection = select_ads_period_raw_files(
                sampling_root=settings.local_sampling_root,
                profile_id=profile_id,
                report_type_id=report_type_id,
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
                incomplete = True
            raw_file_paths_by_report_type[report_type_id] = [
                item.raw_file_path for item in selection.files
            ]
        if incomplete:
            raise SystemExit(2)

    service = AdsIngestionService(
        raw_reports_root=settings.raw_reports_root,
        output_root=args.output_root,
    )
    result = service.run(
        profile_id=profile_id,
        report_type_ids=report_type_ids,
        marketplace_id=args.marketplace_id or settings.amazon_marketplace_id,
        raw_file_paths_by_report_type=raw_file_paths_by_report_type,
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

    print(f"Ads ingestion mode={result.mode} status={result.status}")
    print(result.message)
    print(f"dry_run_output_dir={result.dry_run_result.output_dir}")
    print(
        f"prepared_rows={result.dry_run_result.prepared_row_count} requires_review={result.requires_review} sync_run_id={result.sync_run_id}"
    )
    print(
        f"Ads period ingestion files_processed={result.dry_run_result.processed_file_count} "
        f"prepared_rows={result.dry_run_result.prepared_row_count}"
    )
    if result.upsert_result is not None:
        print(
            f"upsert attempted={result.upsert_result.attempted_rows} inserted={result.upsert_result.inserted_rows} updated={result.upsert_result.updated_rows} "
            f"written={result.upsert_result.written_rows} skipped={result.upsert_result.skipped_rows}"
        )
        for table_result in result.upsert_result.table_results:
            print(
                f"{table_result.table_name}: attempted={table_result.attempted_rows} inserted={table_result.inserted_rows} updated={table_result.updated_rows} "
                f"skipped={table_result.skipped_rows}"
            )
    if result.requires_review and not args.allow_review:
        raise SystemExit(2)


if __name__ == "__main__":
    run_cli_main(main)
