from __future__ import annotations

import argparse
import json
from pathlib import Path

from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.sampling.ads_report_sampling_plan import get_ads_sampling_plan
from seller_data_pipeline.sampling.report_analyzer import analyze_report_file
from seller_data_pipeline.sampling.schema_drift import (
    build_ads_expected_schema,
    render_schema_validation_markdown,
    validate_report_schema,
    write_schema_validation_json,
)

from analyze_ads_downloaded_reports import find_latest_ads_raw_file


DEFAULT_OUTPUT_DIR = "runtime/sampling/schema_validation"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate latest downloaded Amazon Ads raw JSON files against the expected "
            "sampling-plan field schema. This is a pre-ingestion schema-drift guard."
        )
    )
    parser.add_argument("--profile-id", required=True, help="Amazon Ads profile ID.")
    parser.add_argument(
        "--report-type-id",
        action="append",
        default=None,
        help=(
            "Ads reportTypeId to validate. Repeat this option for multiple types. "
            "Defaults to every reportTypeId in the local Ads sampling plan."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for generated schema validation JSON/Markdown files.",
    )
    parser.add_argument(
        "--skip-missing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip missing report types instead of failing. Default: true.",
    )
    parser.add_argument(
        "--fail-on-review",
        action="store_true",
        help="Exit with code 2 if any validation result requires manual review.",
    )
    parser.add_argument(
        "--write-markdown",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Write a Markdown companion file next to each JSON result. Default: true.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    report_type_ids = args.report_type_id or [
        item.report_type_id for item in get_ads_sampling_plan()
    ]
    output_dir = Path(args.output_dir)
    results = []
    skipped = 0

    for report_type_id in report_type_ids:
        raw_file_path = find_latest_ads_raw_file(
            raw_reports_root=settings.raw_reports_root,
            profile_id=args.profile_id,
            report_type_id=report_type_id,
        )
        if raw_file_path is None:
            skipped += 1
            message = (
                "No local Ads raw JSON found for "
                f"profile_id={args.profile_id} report_type_id={report_type_id}"
            )
            if args.skip_missing:
                print(f"Skipped: {message}")
                continue
            raise SystemExit(message)

        analysis = analyze_report_file(
            raw_file_path=str(raw_file_path),
            report_type=report_type_id,
            marketplace_id=args.profile_id,
            source_system="amazon_ads",
            redact_sample_values=True,
        )
        result = validate_report_schema(
            analysis=analysis,
            expected_schema=build_ads_expected_schema(report_type_id),
        )
        output_base = output_dir / f"ADS_{_safe_filename(report_type_id)}_schema_validation"
        json_path = write_schema_validation_json(output_base.with_suffix(".json"), result)
        if args.write_markdown:
            markdown_path = output_base.with_suffix(".md")
            markdown_path.write_text(render_schema_validation_markdown(result), encoding="utf-8")
        results.append(result)
        print(
            f"{report_type_id}: status={result.status} severity={result.severity} "
            f"missing={len(result.missing_fields)} new={len(result.new_fields)} "
            f"row_count={result.row_count} json={json_path}"
        )

    statuses = {
        status: sum(1 for result in results if result.status == status)
        for status in sorted({result.status for result in results})
    }
    summary = {
        "checked": len(results),
        "skipped": skipped,
        "requires_review": sum(1 for result in results if result.requires_review),
        "statuses": statuses,
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    if args.fail_on_review and any(result.requires_review for result in results):
        raise SystemExit(2)


def _safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value)


if __name__ == "__main__":
    main()
