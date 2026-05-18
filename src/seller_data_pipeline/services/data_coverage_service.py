from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class DataCoverageRow:
    data_domain: str
    source_table: str
    business_date_semantics: str
    row_count: int
    dated_row_count: int
    min_business_date: date | None
    max_business_date: date | None
    distinct_business_dates: int
    distinct_entity_count: int
    target_window_row_count: int
    target_min_business_date: date | None
    target_max_business_date: date | None
    latest_created_at: datetime | None
    latest_updated_at: datetime | None
    status: str
    coverage_start_gap_days: int | None
    days_since_latest_business_date: int | None
    notes: str

    @classmethod
    def from_mapping(
        cls,
        row: dict[str, Any],
        *,
        target_start_date: date,
        target_end_date: date,
    ) -> DataCoverageRow:
        row_count = _to_int(row.get("row_count"))
        dated_row_count = _to_int(row.get("dated_row_count"))
        min_date = _as_date(row.get("min_business_date"))
        max_date = _as_date(row.get("max_business_date"))
        target_rows = _to_int(row.get("target_window_row_count"))
        status = classify_coverage_status(
            row_count=row_count,
            dated_row_count=dated_row_count,
            min_business_date=min_date,
            max_business_date=max_date,
            target_window_row_count=target_rows,
            target_start_date=target_start_date,
        )
        return cls(
            data_domain=str(row.get("data_domain") or ""),
            source_table=str(row.get("source_table") or ""),
            business_date_semantics=str(row.get("business_date_semantics") or ""),
            row_count=row_count,
            dated_row_count=dated_row_count,
            min_business_date=min_date,
            max_business_date=max_date,
            distinct_business_dates=_to_int(row.get("distinct_business_dates")),
            distinct_entity_count=_to_int(row.get("distinct_entity_count")),
            target_window_row_count=target_rows,
            target_min_business_date=_as_date(row.get("target_min_business_date")),
            target_max_business_date=_as_date(row.get("target_max_business_date")),
            latest_created_at=_as_datetime(row.get("latest_created_at")),
            latest_updated_at=_as_datetime(row.get("latest_updated_at")),
            status=status,
            coverage_start_gap_days=(min_date - target_start_date).days if min_date and min_date > target_start_date else None,
            days_since_latest_business_date=(target_end_date - max_date).days if max_date else None,
            notes=str(row.get("notes") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "data_domain": self.data_domain,
            "source_table": self.source_table,
            "business_date_semantics": self.business_date_semantics,
            "row_count": self.row_count,
            "dated_row_count": self.dated_row_count,
            "min_business_date": _format_date(self.min_business_date),
            "max_business_date": _format_date(self.max_business_date),
            "distinct_business_dates": self.distinct_business_dates,
            "distinct_entity_count": self.distinct_entity_count,
            "target_window_row_count": self.target_window_row_count,
            "target_min_business_date": _format_date(self.target_min_business_date),
            "target_max_business_date": _format_date(self.target_max_business_date),
            "latest_created_at": _format_datetime(self.latest_created_at),
            "latest_updated_at": _format_datetime(self.latest_updated_at),
            "status": self.status,
            "coverage_start_gap_days": self.coverage_start_gap_days,
            "days_since_latest_business_date": self.days_since_latest_business_date,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ReportRequestCoverageRow:
    source_system: str
    report_type: str
    request_count: int
    done_count: int
    downloaded_count: int
    parsed_count: int
    min_data_start_date: date | None
    max_data_end_date: date | None
    target_overlap_request_count: int
    latest_requested_at: datetime | None
    latest_downloaded_at: datetime | None
    latest_parsed_at: datetime | None

    @classmethod
    def from_mapping(cls, row: dict[str, Any]) -> ReportRequestCoverageRow:
        return cls(
            source_system=str(row.get("source_system") or ""),
            report_type=str(row.get("report_type") or ""),
            request_count=_to_int(row.get("request_count")),
            done_count=_to_int(row.get("done_count")),
            downloaded_count=_to_int(row.get("downloaded_count")),
            parsed_count=_to_int(row.get("parsed_count")),
            min_data_start_date=_as_date(row.get("min_data_start_date")),
            max_data_end_date=_as_date(row.get("max_data_end_date")),
            target_overlap_request_count=_to_int(row.get("target_overlap_request_count")),
            latest_requested_at=_as_datetime(row.get("latest_requested_at")),
            latest_downloaded_at=_as_datetime(row.get("latest_downloaded_at")),
            latest_parsed_at=_as_datetime(row.get("latest_parsed_at")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_system": self.source_system,
            "report_type": self.report_type,
            "request_count": self.request_count,
            "done_count": self.done_count,
            "downloaded_count": self.downloaded_count,
            "parsed_count": self.parsed_count,
            "min_data_start_date": _format_date(self.min_data_start_date),
            "max_data_end_date": _format_date(self.max_data_end_date),
            "target_overlap_request_count": self.target_overlap_request_count,
            "latest_requested_at": _format_datetime(self.latest_requested_at),
            "latest_downloaded_at": _format_datetime(self.latest_downloaded_at),
            "latest_parsed_at": _format_datetime(self.latest_parsed_at),
        }


@dataclass(frozen=True)
class DataCoverageAuditResult:
    marketplace_id: str
    target_start_date: date
    target_end_date: date
    generated_at_utc: datetime
    coverage_rows: tuple[DataCoverageRow, ...]
    report_request_rows: tuple[ReportRequestCoverageRow, ...]
    output_files: dict[str, str]

    @property
    def status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in self.coverage_rows:
            counts[row.status] = counts.get(row.status, 0) + 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "marketplace_id": self.marketplace_id,
            "target_start_date": self.target_start_date.isoformat(),
            "target_end_date": self.target_end_date.isoformat(),
            "generated_at_utc": self.generated_at_utc.isoformat(),
            "status_counts": self.status_counts,
            "coverage_rows": [row.to_dict() for row in self.coverage_rows],
            "report_request_rows": [row.to_dict() for row in self.report_request_rows],
            "output_files": dict(self.output_files),
        }

    def with_output_files(self, output_files: dict[str, str]) -> DataCoverageAuditResult:
        return DataCoverageAuditResult(
            marketplace_id=self.marketplace_id,
            target_start_date=self.target_start_date,
            target_end_date=self.target_end_date,
            generated_at_utc=self.generated_at_utc,
            coverage_rows=self.coverage_rows,
            report_request_rows=self.report_request_rows,
            output_files=output_files,
        )


class DataCoverageRepoProtocol(Protocol):
    def fetch_core_coverage_rows(
        self,
        *,
        marketplace_id: str,
        target_start_date: date,
        target_end_date: date,
    ) -> list[dict[str, Any]]:
        ...

    def fetch_report_request_coverage_rows(
        self,
        *,
        marketplace_id: str,
        target_start_date: date,
        target_end_date: date,
    ) -> list[dict[str, Any]]:
        ...


class DataCoverageAuditService:
    def __init__(self, repo: DataCoverageRepoProtocol) -> None:
        self.repo = repo

    def run(
        self,
        *,
        marketplace_id: str,
        target_start_date: date,
        target_end_date: date,
        output_root: str | Path | None = None,
    ) -> DataCoverageAuditResult:
        if target_end_date < target_start_date:
            raise ValueError("target_end_date must be on or after target_start_date")
        generated_at = datetime.now(UTC).replace(microsecond=0)
        coverage_rows = tuple(
            DataCoverageRow.from_mapping(
                row,
                target_start_date=target_start_date,
                target_end_date=target_end_date,
            )
            for row in self.repo.fetch_core_coverage_rows(
                marketplace_id=marketplace_id,
                target_start_date=target_start_date,
                target_end_date=target_end_date,
            )
        )
        report_request_rows = tuple(
            ReportRequestCoverageRow.from_mapping(row)
            for row in self.repo.fetch_report_request_coverage_rows(
                marketplace_id=marketplace_id,
                target_start_date=target_start_date,
                target_end_date=target_end_date,
            )
        )
        result = DataCoverageAuditResult(
            marketplace_id=marketplace_id,
            target_start_date=target_start_date,
            target_end_date=target_end_date,
            generated_at_utc=generated_at,
            coverage_rows=coverage_rows,
            report_request_rows=report_request_rows,
            output_files={},
        )
        if output_root is not None:
            return write_coverage_files(result=result, output_root=output_root)
        return result


def classify_coverage_status(
    *,
    row_count: int,
    dated_row_count: int,
    min_business_date: date | None,
    max_business_date: date | None,
    target_window_row_count: int,
    target_start_date: date,
) -> str:
    if row_count == 0:
        return "no_rows"
    if dated_row_count == 0 or min_business_date is None or max_business_date is None:
        return "no_business_dates"
    if target_window_row_count == 0:
        return "outside_target_window"
    if min_business_date > target_start_date:
        return "starts_after_target_start"
    return "has_target_window_data"


def write_coverage_files(
    *,
    result: DataCoverageAuditResult,
    output_root: str | Path,
) -> DataCoverageAuditResult:
    root = Path(output_root)
    period_dir = f"{result.target_start_date.isoformat()}_{result.target_end_date.isoformat()}"
    output_dir = root / result.marketplace_id / period_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "data_coverage_audit.json"
    markdown_path = output_dir / "data_coverage_audit.md"
    csv_path = output_dir / "data_coverage_audit.csv"
    request_csv_path = output_dir / "report_request_coverage.csv"

    json_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_coverage_markdown(result), encoding="utf-8")
    write_coverage_csv(result.coverage_rows, csv_path)
    write_report_request_csv(result.report_request_rows, request_csv_path)

    return result.with_output_files(
        {
            "json": str(json_path),
            "markdown": str(markdown_path),
            "coverage_csv": str(csv_path),
            "report_request_csv": str(request_csv_path),
        }
    )


def render_coverage_markdown(result: DataCoverageAuditResult) -> str:
    lines = [
        "# Data Coverage Audit",
        "",
        f"Marketplace: `{result.marketplace_id}`",
        f"Target window: `{result.target_start_date}` to `{result.target_end_date}`",
        f"Generated UTC: `{result.generated_at_utc.isoformat()}`",
        "",
        "## Status summary",
        "",
        "| Status | Count |",
        "|---|---:|",
    ]
    for status, count in sorted(result.status_counts.items()):
        lines.append(f"| `{status}` | {count} |")
    lines.extend(
        [
            "",
            "## Normalized table coverage",
            "",
            "| Data domain | Table | Status | Rows | Business date range | Target rows | Latest business date age | Entities | Date semantics |",
            "|---|---|---|---:|---|---:|---:|---:|---|",
        ]
    )
    for row in result.coverage_rows:
        business_range = f"{_format_date(row.min_business_date)}..{_format_date(row.max_business_date)}"
        lines.append(
            "| {domain} | `{table}` | `{status}` | {rows} | {range} | {target_rows} | {age} | {entities} | {semantics} |".format(
                domain=row.data_domain,
                table=row.source_table,
                status=row.status,
                rows=row.row_count,
                range=business_range,
                target_rows=row.target_window_row_count,
                age="" if row.days_since_latest_business_date is None else row.days_since_latest_business_date,
                entities=row.distinct_entity_count,
                semantics=row.business_date_semantics,
            )
        )
    lines.extend(
        [
            "",
            "## Report request coverage",
            "",
            "| Source | Report type | Requests | Done | Downloaded | Parsed | Requested data window | Target-overlap requests |",
            "|---|---|---:|---:|---:|---:|---|---:|",
        ]
    )
    for row in result.report_request_rows:
        request_range = f"{_format_date(row.min_data_start_date)}..{_format_date(row.max_data_end_date)}"
        lines.append(
            "| {source} | `{report_type}` | {requests} | {done} | {downloaded} | {parsed} | {range} | {target_overlap} |".format(
                source=row.source_system,
                report_type=row.report_type,
                requests=row.request_count,
                done=row.done_count,
                downloaded=row.downloaded_count,
                parsed=row.parsed_count,
                range=request_range,
                target_overlap=row.target_overlap_request_count,
            )
        )
    lines.extend(
        [
            "",
            "## How to read this audit",
            "",
            "- `has_target_window_data`: the table has rows in the requested target window.",
            "- `starts_after_target_start`: the table has rows in the target window, but the earliest business date is after the requested start date.",
            "- `outside_target_window`: the table has rows, but none overlap the requested target window.",
            "- `no_rows`: the table is empty for this marketplace.",
            "- Snapshot-style sources such as Listing, Inventory, FBA Fee Preview, and Promotion product details are not expected to contain every calendar day.",
            "",
        ]
    )
    return "\n".join(lines)


def write_coverage_csv(rows: tuple[DataCoverageRow, ...], path: Path) -> None:
    fieldnames = list(rows[0].to_dict()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_dict())


def write_report_request_csv(rows: tuple[ReportRequestCoverageRow, ...], path: Path) -> None:
    fieldnames = list(rows[0].to_dict()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_dict())


def _to_int(value: Any) -> int:
    if value is None:
        return 0
    return int(value)


def _as_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _format_date(value: date | None) -> str:
    return value.isoformat() if value else ""


def _format_datetime(value: datetime | None) -> str:
    return value.isoformat() if value else ""


__all__ = [
    "DataCoverageAuditResult",
    "DataCoverageAuditService",
    "DataCoverageRow",
    "ReportRequestCoverageRow",
    "classify_coverage_status",
    "write_coverage_files",
]
