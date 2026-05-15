from __future__ import annotations

import argparse
from pathlib import Path

from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.parsers.amazon.ads_report_parser import AdsReportParser
from seller_data_pipeline.sampling.report_analyzer import (
    analyze_report_file,
    render_report_analysis_markdown,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze a downloaded Amazon Ads raw JSON report and write a redacted field sample. "
            "Pass --latest to analyze the newest local raw file for a profile/report type."
        )
    )
    parser.add_argument(
        "--raw-file",
        default=None,
        help="Path to a downloaded Ads raw JSON file. Optional when --latest is used.",
    )
    parser.add_argument("--report-type-id", required=True, help="Example: spCampaigns")
    parser.add_argument("--profile-id", required=True, help="Amazon Ads profile ID.")
    parser.add_argument(
        "--latest",
        action="store_true",
        help=(
            "Analyze the newest downloaded raw JSON file under "
            "reports/raw/amazon_ads/{profile_id}/{report_type_id}/."
        ),
    )
    parser.add_argument(
        "--output-md",
        default=None,
        help="Optional markdown output path. Defaults to stdout only.",
    )
    parser.add_argument(
        "--show-raw-sample-values",
        action="store_true",
        help="Show raw sample values instead of redacted values. Do not use for committed docs.",
    )
    parser.add_argument(
        "--validate-parser",
        action="store_true",
        help="Also run the generic Ads parser and print normalized row count.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    raw_file_path = _resolve_raw_file_path(
        raw_file_arg=args.raw_file,
        latest=args.latest,
        raw_reports_root=settings.raw_reports_root,
        profile_id=args.profile_id,
        report_type_id=args.report_type_id,
    )
    print(f"Analyzing Ads raw file: {raw_file_path}")
    analysis = analyze_report_file(
        raw_file_path=str(raw_file_path),
        report_type=args.report_type_id,
        marketplace_id=args.profile_id,
        source_system="amazon_ads",
        redact_sample_values=not args.show_raw_sample_values,
    )
    markdown = render_report_analysis_markdown(analysis)
    if args.output_md:
        output_path = Path(args.output_md)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        print(f"Wrote Ads report analysis markdown: {output_path}")
    else:
        print(markdown)

    if args.validate_parser:
        records = AdsReportParser().parse_file(
            raw_file_path=str(raw_file_path),
            profile_id=args.profile_id,
            report_type_id=args.report_type_id,
        )
        print(f"Ads parser normalized_rows={len(records)}")


def _resolve_raw_file_path(
    *,
    raw_file_arg: str | None,
    latest: bool,
    raw_reports_root: str,
    profile_id: str,
    report_type_id: str,
) -> Path:
    if raw_file_arg and latest:
        raise SystemExit("Use either --raw-file or --latest, not both.")
    if raw_file_arg:
        path = Path(raw_file_arg)
        if not path.exists():
            raise SystemExit(f"Ads raw file does not exist: {path}")
        return path
    if not latest:
        raise SystemExit("Either --raw-file or --latest is required.")

    root = Path(raw_reports_root) / "amazon_ads" / str(profile_id) / str(report_type_id)
    if not root.exists():
        raise SystemExit(f"No Ads raw report directory found: {root}")
    candidates = [path for path in root.rglob("*.json") if path.is_file()]
    if not candidates:
        raise SystemExit(f"No Ads raw JSON files found under: {root}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


if __name__ == "__main__":
    main()
