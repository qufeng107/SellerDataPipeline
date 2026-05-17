from __future__ import annotations

import argparse
from pathlib import Path

from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.config.settings import get_settings
from seller_data_pipeline.sampling.report_analyzer import (
    analyze_report_file,
    render_report_analysis_markdown,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze a downloaded Amazon raw report and optionally write markdown sample docs."
        )
    )
    parser.add_argument("--raw-file", required=True, help="Path to a downloaded raw report file.")
    parser.add_argument("--report-type", required=True, help="Amazon report type value.")
    parser.add_argument("--marketplace-id", default=None, help="Amazon marketplace ID.")
    parser.add_argument(
        "--output-md",
        default=None,
        help="Optional markdown output path. Defaults to stdout only.",
    )
    parser.add_argument(
        "--show-raw-sample-values",
        action="store_true",
        help=(
            "Show raw sample values instead of redacted values. Do not use this for committed docs."
        ),
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    analysis = analyze_report_file(
        raw_file_path=args.raw_file,
        report_type=args.report_type,
        marketplace_id=args.marketplace_id,
        redact_sample_values=not args.show_raw_sample_values,
    )
    markdown = render_report_analysis_markdown(analysis)
    if args.output_md:
        output_path = Path(args.output_md)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        print(f"Wrote report analysis markdown: {output_path}")
    else:
        print(markdown)


if __name__ == "__main__":
    main()
