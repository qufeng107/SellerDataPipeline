from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class RawReportPreview:
    delimiter: str | None
    encoding: str
    header: list[str]
    sample_rows: list[dict[str, str]]
    row_count_previewed: int


@dataclass(frozen=True)
class SavedRawReport:
    file_path: Path
    checksum_sha256: str
    size_bytes: int
    preview: RawReportPreview


class RawReportFileStore:
    """Stores downloaded Amazon report bytes and extracts a small local preview."""

    def __init__(self, *, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def save_report_bytes(
        self,
        *,
        report_type: str,
        marketplace_ids: list[str],
        report_id: str,
        content: bytes,
    ) -> SavedRawReport:
        marketplace = marketplace_ids[0] if marketplace_ids else "unknown-marketplace"
        date_dir = datetime.now(UTC).strftime("%Y-%m-%d")
        file_path = (
            self.root_dir
            / "amazon"
            / self._safe_path_part(marketplace)
            / self._safe_path_part(report_type)
            / date_dir
            / f"{self._safe_path_part(report_id)}.txt"
        )
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)
        return SavedRawReport(
            file_path=file_path,
            checksum_sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            preview=preview_report_bytes(content),
        )

    @staticmethod
    def _safe_path_part(value: str) -> str:
        safe = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value)
        return safe[:120] or "unknown"


def preview_report_bytes(content: bytes, *, sample_row_limit: int = 5) -> RawReportPreview:
    text, encoding = _decode_report_content(content)
    delimiter = _detect_delimiter(text)
    if delimiter is None:
        first_line = text.splitlines()[0] if text.splitlines() else ""
        header = [first_line] if first_line else []
        return RawReportPreview(
            delimiter=None,
            encoding=encoding,
            header=header,
            sample_rows=[],
            row_count_previewed=0,
        )
    lines = text.splitlines()
    if not lines:
        return RawReportPreview(
            delimiter=delimiter,
            encoding=encoding,
            header=[],
            sample_rows=[],
            row_count_previewed=0,
        )
    reader = csv.DictReader(lines, delimiter=delimiter)
    header = list(reader.fieldnames or [])
    sample_rows: list[dict[str, str]] = []
    for row in reader:
        sample_rows.append({key: value for key, value in row.items() if key is not None})
        if len(sample_rows) >= sample_row_limit:
            break
    return RawReportPreview(
        delimiter=delimiter,
        encoding=encoding,
        header=header,
        sample_rows=sample_rows,
        row_count_previewed=len(sample_rows),
    )


def _decode_report_content(content: bytes) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return content.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace"), "utf-8-replace"


def _detect_delimiter(text: str) -> str | None:
    first_non_empty_line = next((line for line in text.splitlines() if line.strip()), "")
    if not first_non_empty_line:
        return None
    tab_count = first_non_empty_line.count("\t")
    comma_count = first_non_empty_line.count(",")
    if tab_count == 0 and comma_count == 0:
        return None
    return "\t" if tab_count >= comma_count else ","
