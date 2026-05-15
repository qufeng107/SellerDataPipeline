from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SENSITIVE_FIELDS = {
    "campaign_name",
    "ad_group_name",
    "keyword",
    "targeting",
    "search_term",
    "advertised_asin",
    "advertised_sku",
    "purchased_asin",
    "raw_data",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Safely inspect UTF-8 ingestion preview JSONL files. This avoids Windows "
            "PowerShell codepage mojibake and can redact sensitive Ads strategy fields."
        )
    )
    parser.add_argument("preview_file", help="Path to a *.preview.jsonl file.")
    parser.add_argument("--limit", type=int, default=2, help="Number of rows to print.")
    parser.add_argument(
        "--show-sensitive",
        action="store_true",
        help="Show sensitive strategy fields instead of redacting them.",
    )
    args = parser.parse_args()

    path = Path(args.preview_file)
    if not path.exists():
        raise SystemExit(f"Preview file not found: {path}")

    printed = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            if not args.show_sensitive:
                row = redact_sensitive_fields(row)
            print(json.dumps(row, ensure_ascii=False, indent=2, sort_keys=True))
            printed += 1
            if printed >= args.limit:
                break


def redact_sensitive_fields(row: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(row)
    for field in SENSITIVE_FIELDS:
        if field in redacted and redacted[field] not in (None, ""):
            redacted[field] = "<redacted>"
    return redacted


if __name__ == "__main__":
    main()
