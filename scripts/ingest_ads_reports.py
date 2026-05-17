from __future__ import annotations

import argparse
import json
from pathlib import Path

from seller_data_pipeline.common.cli import run_cli_main
from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.ingestion.ads_ingestion import AdsIngestionService


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
    parser.add_argument(
        "--output-root",
        default="runtime/ingestion/amazon_ads",
        help="Root directory for preview rows and audit manifests.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Actually connect to Azure SQL and upsert rows. "
            "Without this flag, no DB writes occur."
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

    service = AdsIngestionService(
        raw_reports_root=settings.raw_reports_root,
        output_root=args.output_root,
    )
    result = service.run(
        profile_id=profile_id,
        report_type_ids=args.report_type_id,
        marketplace_id=args.marketplace_id or settings.amazon_marketplace_id,
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
        "prepared_rows={prepared} requires_review={review} sync_run_id={run_id}".format(
            prepared=result.dry_run_result.prepared_row_count,
            review=result.requires_review,
            run_id=result.sync_run_id,
        )
    )
    if result.upsert_result is not None:
        print(
            "upsert attempted={attempted} inserted={inserted} updated={updated} "
            "written={written} skipped={skipped}".format(
                attempted=result.upsert_result.attempted_rows,
                inserted=result.upsert_result.inserted_rows,
                updated=result.upsert_result.updated_rows,
                written=result.upsert_result.written_rows,
                skipped=result.upsert_result.skipped_rows,
            )
        )
        for table_result in result.upsert_result.table_results:
            print(
                "{table}: attempted={attempted} inserted={inserted} updated={updated} "
                "skipped={skipped}".format(
                    table=table_result.table_name,
                    attempted=table_result.attempted_rows,
                    inserted=table_result.inserted_rows,
                    updated=table_result.updated_rows,
                    skipped=table_result.skipped_rows,
                )
            )
    if result.requires_review and not args.allow_review:
        raise SystemExit(2)


if __name__ == "__main__":
    run_cli_main(main)
