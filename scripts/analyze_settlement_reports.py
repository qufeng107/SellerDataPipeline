from __future__ import annotations

import argparse
from pathlib import Path

from seller_data_pipeline.common.logging import configure_logging
from seller_data_pipeline.sampling.settlement_analyzer import (
    analyze_settlement_report_files,
    render_settlement_aggregate_markdown,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze multiple downloaded Amazon settlement reports."
    )
    parser.add_argument(
        "--raw-dir",
        required=True,
        help="Directory containing downloaded settlement .txt raw files.",
    )
    parser.add_argument(
        "--marketplace-id",
        default="ATVPDKIKX0DER",
        help="Amazon marketplace ID used for the downloaded reports.",
    )
    parser.add_argument(
        "--output-md",
        default="requirements/data_samples/GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2.md",
        help="Markdown output path for the aggregate settlement analysis.",
    )
    return parser.parse_args()


def main() -> None:
    configure_logging()
    args = parse_args()
    raw_dir = Path(args.raw_dir)
    raw_file_paths = sorted(raw_dir.glob("*.txt"))
    if not raw_file_paths:
        raise SystemExit(f"No .txt settlement raw files found under: {raw_dir}")

    analysis = analyze_settlement_report_files(
        raw_file_paths=raw_file_paths,
        marketplace_id=args.marketplace_id,
    )
    markdown = render_settlement_aggregate_markdown(analysis)
    output_path = Path(args.output_md)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    print(f"Analyzed {len(raw_file_paths)} settlement report file(s).")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
