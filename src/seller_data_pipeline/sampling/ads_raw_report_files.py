from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from seller_data_pipeline.sampling.raw_report_files import decode_report_content


@dataclass(frozen=True)
class AdsRawReportPreview:
    encoding: str
    file_format: str
    row_count_previewed: int
    sample_rows: list[dict[str, Any]]
    top_level_type: str


@dataclass(frozen=True)
class SavedAdsRawReport:
    file_path: Path
    checksum_sha256: str
    size_bytes: int
    preview: AdsRawReportPreview


class AdsRawReportFileStore:
    """Stores downloaded Amazon Ads report bytes under reports/raw/amazon_ads/."""

    def __init__(self, *, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def save_report_bytes(
        self,
        *,
        profile_id: str,
        report_type_id: str,
        report_id: str,
        content: bytes,
    ) -> SavedAdsRawReport:
        date_dir = datetime.now(UTC).strftime("%Y-%m-%d")
        file_path = (
            self.root_dir
            / "amazon_ads"
            / self._safe_path_part(profile_id)
            / self._safe_path_part(report_type_id)
            / date_dir
            / f"{self._safe_path_part(report_id)}.json"
        )
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)
        return SavedAdsRawReport(
            file_path=file_path,
            checksum_sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            preview=preview_ads_report_bytes(content),
        )

    @staticmethod
    def _safe_path_part(value: str) -> str:
        safe = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value)
        return safe[:120] or "unknown"


def preview_ads_report_bytes(content: bytes, *, sample_row_limit: int = 5) -> AdsRawReportPreview:
    text, encoding = decode_report_content(content)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        first_line = text.splitlines()[0] if text.splitlines() else ""
        sample = [{"first_line": first_line[:500]}] if first_line else []
        return AdsRawReportPreview(
            encoding=encoding,
            file_format="text",
            row_count_previewed=len(sample),
            sample_rows=sample,
            top_level_type="text",
        )

    if isinstance(payload, list):
        rows = [item for item in payload if isinstance(item, dict)]
        return AdsRawReportPreview(
            encoding=encoding,
            file_format="json",
            row_count_previewed=min(len(rows), sample_row_limit),
            sample_rows=rows[:sample_row_limit],
            top_level_type="list",
        )
    if isinstance(payload, dict):
        rows = _find_first_list_of_objects(payload)
        return AdsRawReportPreview(
            encoding=encoding,
            file_format="json",
            row_count_previewed=min(len(rows), sample_row_limit),
            sample_rows=rows[:sample_row_limit],
            top_level_type="object",
        )
    return AdsRawReportPreview(
        encoding=encoding,
        file_format="json",
        row_count_previewed=0,
        sample_rows=[],
        top_level_type=type(payload).__name__,
    )


def _find_first_list_of_objects(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for value in payload.values():
        if isinstance(value, list) and all(isinstance(item, dict) for item in value):
            return value
    return []
