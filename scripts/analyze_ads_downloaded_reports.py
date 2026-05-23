from __future__ import annotations

import argparse
from pathlib import Path

from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.parsers.amazon.ads_report_parser import AdsReportParser
from seller_data_pipeline.sampling.ads_report_sampling_plan import get_ads_sampling_plan
from seller_data_pipeline.sampling.report_analyzer import (
    analyze_report_file,
    render_report_analysis_markdown,
)
from seller_data_pipeline.sampling.schema_drift import (
    build_ads_expected_schema,
    validate_report_schema,
    write_schema_validation_json,
)

DEFAULT_OUTPUT_DIR = "docs/data_access/sample_notes"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze the newest downloaded Amazon Ads raw JSON files for one or more "
            "report types and write redacted ADS_*.md sample documents."
        )
    )
    parser.add_argument("--profile-id", required=True, help="Amazon Ads profile ID.")
    parser.add_argument(
        "--report-type-id",
        action="append",
        default=None,
        help=(
            "Ads reportTypeId to analyze. Repeat this option for multiple types. "
            "Defaults to every reportTypeId in the local Ads sampling plan."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for generated ADS_<reportTypeId>.md files.",
    )
    parser.add_argument(
        "--show-raw-sample-values",
        action="store_true",
        help="Show raw sample values instead of redacted values. Do not use for committed docs.",
    )
    parser.add_argument(
        "--validate-parser",
        action="store_true",
        help="Also run the generic Ads parser and print normalized row count for each report.",
    )
    parser.add_argument(
        "--skip-missing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip missing report types instead of failing. Default: true.",
    )
    parser.add_argument(
        "--validate-schema",
        action="store_true",
        help=(
            "Also compare observed fields with the Ads sampling-plan schema and write "
            "runtime/sampling/schema_validation JSON results."
        ),
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    report_type_ids = args.report_type_id or [
        item.report_type_id for item in get_ads_sampling_plan()
    ]
    output_dir = Path(args.output_dir)
    written = 0
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
            redact_sample_values=not args.show_raw_sample_values,
        )
        markdown = render_report_analysis_markdown(analysis)
        output_path = build_ads_sample_output_path(output_dir, report_type_id)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        written += 1
        print(f"Wrote {output_path} from {raw_file_path}")

        if args.validate_parser:
            records = AdsReportParser().parse_file(
                raw_file_path=str(raw_file_path),
                profile_id=args.profile_id,
                report_type_id=report_type_id,
            )
            print(f"{report_type_id}: Ads parser normalized_rows={len(records)}")

        if args.validate_schema:
            result = validate_report_schema(
                analysis=analysis,
                expected_schema=build_ads_expected_schema(report_type_id),
            )
            validation_path = (
                Path("runtime/sampling/schema_validation")
                / f"ADS_{_safe_report_type(report_type_id)}_schema_validation.json"
            )
            write_schema_validation_json(validation_path, result)
            print(
                f"{report_type_id}: schema_validation_status={result.status} "
                f"requires_review={result.requires_review}"
            )

    print(f"Done. written={written} skipped={skipped}")


def find_latest_ads_raw_file(
    *,
    raw_reports_root: str,
    profile_id: str,
    report_type_id: str,
) -> Path | None:
    root = Path(raw_reports_root) / "amazon_ads" / str(profile_id) / str(report_type_id)
    if not root.exists():
        return None
    candidates = [path for path in root.rglob("*.json") if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def build_ads_sample_output_path(output_dir: Path, report_type_id: str) -> Path:
    return output_dir / f"ADS_{_safe_report_type(report_type_id)}.md"


def _safe_report_type(report_type_id: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in report_type_id)


if __name__ == "__main__":
    main()
