from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from seller_data_pipeline.sampling.raw_report_files import (
    decode_report_content,
    detect_report_delimiter,
)


@dataclass(frozen=True)
class ParsedFlatFileRow:
    """Generic parsed row for Amazon tab-delimited reports during sampling."""

    marketplace_id: str
    source_report_type: str
    source_report_id: str | None
    source_raw_file_path: str | None
    source_row_hash: str
    raw_data: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AmazonFlatFileParser:
    """Reusable parser base for SP-API tab-delimited flat-file reports."""

    report_type: str = "UNKNOWN"
    required_fields: set[str] = set()

    def parse_file(
        self,
        *,
        raw_file_path: str | Path,
        marketplace_id: str,
        source_report_id: str | None = None,
    ) -> list[Any]:
        path = Path(raw_file_path)
        return self.parse_bytes(
            content=path.read_bytes(),
            marketplace_id=marketplace_id,
            source_report_id=source_report_id,
            source_raw_file_path=str(path),
        )

    def parse_bytes(
        self,
        *,
        content: bytes,
        marketplace_id: str,
        source_report_id: str | None = None,
        source_raw_file_path: str | None = None,
    ) -> list[Any]:
        text, _encoding = decode_report_content(content)
        return self.parse_text(
            text=text,
            marketplace_id=marketplace_id,
            source_report_id=source_report_id,
            source_raw_file_path=source_raw_file_path,
        )

    def parse_text(
        self,
        *,
        text: str,
        marketplace_id: str,
        source_report_id: str | None = None,
        source_raw_file_path: str | None = None,
    ) -> list[Any]:
        delimiter = detect_report_delimiter(text)
        if delimiter is None:
            raise ValueError(f"{self.report_type} must be a delimited flat file")

        reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
        fieldnames = set(reader.fieldnames or [])
        missing_fields = sorted(self.required_fields - fieldnames)
        if missing_fields:
            raise ValueError(f"Missing required {self.report_type} fields: {missing_fields}")

        records: list[Any] = []
        for raw_row in reader:
            row = normalize_row(raw_row)
            if not row:
                continue
            records.append(
                self.row_to_record(
                    row=row,
                    marketplace_id=marketplace_id,
                    source_report_id=source_report_id,
                    source_raw_file_path=source_raw_file_path,
                )
            )
        return records

    def parse(self, content: str) -> list[dict[str, Any]]:
        records = self.parse_text(text=content, marketplace_id="UNKNOWN")
        return [_record_to_dict(record) for record in records]

    def row_to_record(
        self,
        *,
        row: dict[str, str],
        marketplace_id: str,
        source_report_id: str | None,
        source_raw_file_path: str | None,
    ) -> ParsedFlatFileRow:
        return ParsedFlatFileRow(
            marketplace_id=marketplace_id,
            source_report_type=self.report_type,
            source_report_id=source_report_id,
            source_raw_file_path=source_raw_file_path,
            source_row_hash=compute_source_row_hash(row),
            raw_data=row,
        )


def normalize_row(raw_row: dict[Any, Any]) -> dict[str, str]:
    return {str(key): (value or "").strip() for key, value in raw_row.items() if key}


def compute_source_row_hash(row: dict[str, str]) -> str:
    canonical = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def empty_to_none(value: Any) -> str | None:
    value = str(value or "").strip()
    return value or None


def parse_int(value: str | None) -> int | None:
    value = (value or "").strip().replace(",", "")
    if not value:
        return None
    return int(Decimal(value))


def parse_decimal(value: str | None) -> Decimal | None:
    value = (value or "").strip().replace(",", "")
    if not value or value in {"--", "—", "N/A", "n/a", "NA", "na"}:
        return None
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal value: {value!r}") from exc


def parse_bool(value: str | None) -> bool | None:
    value = (value or "").strip().lower()
    if not value:
        return None
    if value in {"true", "t", "yes", "y", "1"}:
        return True
    if value in {"false", "f", "no", "n", "0"}:
        return False
    return None


def decimal_to_str(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def serialize_decimals(payload: dict[str, Any], fields: Iterable[str]) -> dict[str, Any]:
    for field in fields:
        if isinstance(payload.get(field), Decimal):
            payload[field] = str(payload[field])
    return payload


def _record_to_dict(record: Any) -> dict[str, Any]:
    if hasattr(record, "to_dict"):
        return record.to_dict()
    if hasattr(record, "__dataclass_fields__"):
        return asdict(record)
    if isinstance(record, dict):
        return record
    raise TypeError(f"Unsupported record type: {type(record)!r}")
