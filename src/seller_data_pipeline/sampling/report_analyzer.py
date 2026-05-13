from __future__ import annotations

import csv
import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from seller_data_pipeline.sampling.raw_report_files import (
    detect_report_delimiter,
    decode_report_content,
)

DEFAULT_SENSITIVE_FIELD_PATTERNS = (
    "sku",
    "asin",
    "listing-id",
    "product-id",
    "item-name",
    "item-description",
    "image-url",
    "title",
    "description",
    "email",
    "name",
    "address",
    "phone",
)

DATE_FIELD_PATTERN = re.compile(r"(^|[-_ ])date($|[-_ ])|open-date|created|updated", re.I)


@dataclass(frozen=True)
class FieldAnalysis:
    position: int
    source_field_name: str
    non_empty_count: int
    empty_count: int
    non_empty_rate: float
    unique_non_empty_count: int
    data_type_suggestion: str
    mapping_status: str
    sample_values: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReportAnalysis:
    report_type: str
    marketplace_id: str | None
    raw_file_path: str
    encoding: str
    delimiter: str | None
    row_count: int
    column_count: int
    fields: list[FieldAnalysis]

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_type": self.report_type,
            "marketplace_id": self.marketplace_id,
            "raw_file_path": self.raw_file_path,
            "encoding": self.encoding,
            "delimiter": self.delimiter,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "fields": [field.to_dict() for field in self.fields],
        }


def analyze_delimited_report_file(
    *,
    raw_file_path: str | Path,
    report_type: str,
    marketplace_id: str | None = None,
    sample_value_limit: int = 5,
    redact_sample_values: bool = True,
) -> ReportAnalysis:
    """Analyze a local Amazon flat-file report without requiring database tables."""

    path = Path(raw_file_path)
    content = path.read_bytes()
    text, encoding = decode_report_content(content)
    delimiter = detect_report_delimiter(text)
    if delimiter is None:
        return ReportAnalysis(
            report_type=report_type,
            marketplace_id=marketplace_id,
            raw_file_path=str(path),
            encoding=encoding,
            delimiter=None,
            row_count=0,
            column_count=0,
            fields=[],
        )

    lines = text.splitlines()
    reader = csv.DictReader(lines, delimiter=delimiter)
    header = list(reader.fieldnames or [])
    stats = {
        field: {
            "non_empty": 0,
            "empty": 0,
            "unique_values": set(),
            "sample_values": [],
        }
        for field in header
    }
    row_count = 0
    for row in reader:
        row_count += 1
        for field in header:
            value = (row.get(field) or "").strip()
            field_stats = stats[field]
            if value:
                field_stats["non_empty"] += 1
                field_stats["unique_values"].add(value)
                sample_values = field_stats["sample_values"]
                if len(sample_values) < sample_value_limit and value not in sample_values:
                    sample_values.append(value)
            else:
                field_stats["empty"] += 1

    fields: list[FieldAnalysis] = []
    for position, field in enumerate(header, start=1):
        field_stats = stats[field]
        sample_values_raw = list(field_stats["sample_values"])
        fields.append(
            FieldAnalysis(
                position=position,
                source_field_name=field,
                non_empty_count=int(field_stats["non_empty"]),
                empty_count=int(field_stats["empty"]),
                non_empty_rate=_safe_rate(int(field_stats["non_empty"]), row_count),
                unique_non_empty_count=len(field_stats["unique_values"]),
                data_type_suggestion=infer_data_type(field, sample_values_raw),
                mapping_status=suggest_mapping_status(field, sample_values_raw),
                sample_values=[
                    redact_sample_value(field, value) if redact_sample_values else value
                    for value in sample_values_raw
                ],
            )
        )

    return ReportAnalysis(
        report_type=report_type,
        marketplace_id=marketplace_id,
        raw_file_path=str(path),
        encoding=encoding,
        delimiter=delimiter,
        row_count=row_count,
        column_count=len(header),
        fields=fields,
    )


def render_report_analysis_markdown(analysis: ReportAnalysis) -> str:
    delimiter_label = "tab" if analysis.delimiter == "\t" else analysis.delimiter or "unknown"
    lines = [
        f"# {analysis.report_type} 字段取样记录",
        "",
        "> 本文件记录真实 Amazon report 样例的字段结构和初步映射建议。",
        (
            "> 原始报告文件可能包含经营数据，不应提交 GitHub；"
            "本文只保留字段统计和脱敏样例。"
        ),
        "",
        "## 1. 样例元数据",
        "",
        "| 项目 | 值 |",
        "|---|---|",
        f"| source_system | `sp_api_reports` |",
        f"| report_type | `{analysis.report_type}` |",
        f"| marketplace_id | `{analysis.marketplace_id or 'unknown'}` |",
        f"| raw_file_path | `{analysis.raw_file_path}` |",
        f"| encoding | `{analysis.encoding}` |",
        f"| delimiter | `{delimiter_label}` |",
        f"| row_count | `{analysis.row_count}` |",
        f"| column_count | `{analysis.column_count}` |",
        "",
        "## 2. 字段统计",
        "",
        (
            "| # | source_field_name | non_empty | empty | non_empty_rate | "
            "unique | type_suggestion | mapping_status | sample_values |"
        ),
        "|---:|---|---:|---:|---:|---:|---|---|---|",
    ]
    for field in analysis.fields:
        sample_values = ", ".join(f"`{_escape_markdown(value)}`" for value in field.sample_values)
        lines.append(
            "| {position} | `{name}` | {non_empty} | {empty} | {rate:.2f} | {unique} | "
            "`{dtype}` | `{status}` | {samples} |".format(
                position=field.position,
                name=field.source_field_name,
                non_empty=field.non_empty_count,
                empty=field.empty_count,
                rate=field.non_empty_rate,
                unique=field.unique_non_empty_count,
                dtype=field.data_type_suggestion,
                status=field.mapping_status,
                samples=sample_values or "-",
            )
        )
    lines.extend(
        [
            "",
            "## 3. 初步结论",
            "",
            (
                "1. 本报告适合生成 `amazon_listing_snapshot`，用于维护 SKU / ASIN / "
                "Listing / 价格 / 状态等基础信息。"
            ),
            (
                "2. FBA 商品在本次样例中 `quantity` 和 `pending-quantity` 为空，"
                "因此不应把本报告作为 FBA 可用库存的唯一来源。"
            ),
            (
                "3. 长文本、图片、zshop 旧字段等暂缓进入正式列，"
                "优先保留在 `raw_data` 和 raw file 中。"
            ),
            (
                "4. 后续需要继续取样库存、销售、财务、广告报告，"
                "再确认 L3 normalized 表和 L4 reporting 表。"
            ),
            "",
            "## 4. 建议目标表",
            "",
            "| 目标表 | 设计状态 | 说明 |",
            "|---|---|---|",
            (
                "| `amazon_listing_snapshot` | `sampling` | "
                "已有第一份真实样例，可先实现 parser 和字段映射，"
                "暂不执行 SQL |"
            ),
            (
                "| `amazon_inventory_daily` | `sampling` | "
                "需要另取 FBA inventory 样例确认真实库存口径 |"
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def infer_data_type(field_name: str, values: list[str]) -> str:
    non_empty_values = [value.strip() for value in values if value.strip()]
    if not non_empty_values:
        return "string"
    if field_name in {"product-id-type", "item-condition"}:
        return "enum_code"
    lowered_values = {value.lower() for value in non_empty_values}
    if lowered_values <= {"y", "n", "yes", "no", "true", "false", "0", "1"}:
        return "boolean_flag"
    if all(_is_integer(value) for value in non_empty_values):
        return "integer"
    if all(_is_decimal(value) for value in non_empty_values):
        return "decimal"
    if DATE_FIELD_PATTERN.search(field_name):
        return "datetime_string"
    return "string"


def suggest_mapping_status(field_name: str, values: list[str]) -> str:
    if field_name in {
        "listing-id",
        "seller-sku",
        "asin1",
        "product-id",
        "product-id-type",
        "item-name",
        "item-description",
        "price",
        "quantity",
        "open-date",
        "item-is-marketplace",
        "item-condition",
        "pending-quantity",
        "fulfillment-channel",
        "merchant-shipping-group",
        "status",
    }:
        return "mapped_candidate"
    if not values:
        return "deferred"
    return "deferred"


def redact_sample_value(field_name: str, value: str) -> str:
    if not value:
        return ""
    normalized_name = field_name.lower()
    if normalized_name in {"product-id-type", "item-condition"}:
        return value[:80] + ("..." if len(value) > 80 else "")
    if any(pattern in normalized_name for pattern in DEFAULT_SENSITIVE_FIELD_PATTERNS):
        return f"<redacted:{len(value)} chars>"
    return value[:80] + ("..." if len(value) > 80 else "")


def _safe_rate(non_empty_count: int, row_count: int) -> float:
    if row_count <= 0:
        return 0.0
    return round(non_empty_count / row_count, 4)


def _is_integer(value: str) -> bool:
    try:
        int(value)
    except ValueError:
        return False
    return True


def _is_decimal(value: str) -> bool:
    try:
        Decimal(value)
    except InvalidOperation:
        return False
    return True


def _escape_markdown(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
