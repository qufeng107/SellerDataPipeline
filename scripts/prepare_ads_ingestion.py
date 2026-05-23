from __future__ import annotations

import argparse

from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.ingestion.ads_ingestion_dry_run import AdsIngestionDryRunService


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare Amazon Ads DB-ready preview rows from downloaded raw reports. "
            "This is a dry-run guardrail and does not connect to Azure SQL."
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
        help="Amazon marketplace ID to stamp on preview rows, for example ATVPDKIKX0DER.",
    )
    parser.add_argument(
        "--report-type-id",
        action="append",
        default=None,
        help=(
            "Ads reportTypeId to prepare. Repeat for multiple report types. "
            "Defaults to all table-ready Ads report mappings."
        ),
    )
    parser.add_argument(
        "--output-root",
        default="runtime/ingestion/amazon_ads",
        help="Root directory for preview rows and audit manifests.",
    )
    parser.add_argument(
        "--fail-on-review",
        action="store_true",
        help="Exit non-zero if any report requires manual schema/table review.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    profile_id = args.profile_id or settings.amazon_ads_profile_id
    if not profile_id:
        raise SystemExit("Missing --profile-id or AMAZON_ADS_PROFILE_ID.")

    service = AdsIngestionDryRunService(
        raw_reports_root=settings.raw_reports_root,
        output_root=args.output_root,
    )
    result = service.prepare(
        profile_id=profile_id,
        report_type_ids=args.report_type_id,
        marketplace_id=args.marketplace_id or settings.amazon_marketplace_id,
        fail_on_review=args.fail_on_review,
    )

    print(f"Ads ingestion dry-run status={result.status}")
    print(f"output_dir={result.output_dir}")
    print(
        f"processed_files={result.processed_file_count} parsed_rows={result.parsed_row_count} prepared_rows={result.prepared_row_count} "
        f"preview_files={result.preview_file_count} requires_review={result.requires_review}"
    )
    for report_result in result.report_results:
        print(
            "{report}: target={target} schema={schema} parsed={parsed} prepared={prepared} "
            "skipped={skipped} review={review}".format(
                report=report_result.report_type_id,
                target=report_result.target_table or "-",
                schema=report_result.schema_validation_status or "-",
                parsed=report_result.parsed_row_count,
                prepared=report_result.prepared_row_count,
                skipped=report_result.skipped,
                review=report_result.requires_review,
            )
        )
        if report_result.preview_file_path:
            print(f"  preview={report_result.preview_file_path}")
        if report_result.skip_reason:
            print(f"  skip_reason={report_result.skip_reason}")
    if args.fail_on_review and result.requires_review:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
