from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class PeriodRawFile:
    report_id: str
    raw_file_path: str
    start_date: date
    end_date: date
    updated_at_utc: str | None = None


@dataclass(frozen=True)
class PeriodRawFileSelection:
    source_system: str
    report_type: str
    target_start_date: date
    target_end_date: date
    files: tuple[PeriodRawFile, ...]
    coverage_complete: bool
    missing_ranges: tuple[tuple[date, date], ...]

    @property
    def selected_file_count(self) -> int:
        return len(self.files)


def select_sp_api_period_raw_files(
    *,
    sampling_root: str | Path,
    marketplace_id: str,
    report_type: str,
    start_date: date,
    end_date: date,
) -> PeriodRawFileSelection:
    _validate_window(start_date=start_date, end_date=end_date)
    manifests_dir = Path(sampling_root) / "report_requests"
    candidates: list[PeriodRawFile] = []
    for manifest in _iter_json_objects(manifests_dir):
        if str(manifest.get("report_type") or "") != report_type:
            continue
        marketplace_ids = manifest.get("marketplace_ids")
        if not isinstance(marketplace_ids, list) or marketplace_id not in {
            str(item) for item in marketplace_ids
        }:
            continue
        if str(manifest.get("processing_status") or "").upper() != "DONE":
            continue
        if str(manifest.get("download_status") or "").upper() != "DOWNLOADED":
            continue
        raw_file_path = str(manifest.get("raw_file_path") or "")
        if not raw_file_path or not Path(raw_file_path).is_file():
            continue
        data_start = _as_datetime(manifest.get("data_start_time"))
        data_end_exclusive = _as_datetime(manifest.get("data_end_time"))
        if data_start is None or data_end_exclusive is None or data_end_exclusive <= data_start:
            continue
        interval_start = data_start.date()
        interval_end = (data_end_exclusive - timedelta(microseconds=1)).date()
        if not _overlaps(
            interval_start,
            interval_end,
            target_start=start_date,
            target_end=end_date,
        ):
            continue
        candidates.append(
            PeriodRawFile(
                report_id=str(manifest.get("report_id") or Path(raw_file_path).stem),
                raw_file_path=raw_file_path,
                start_date=interval_start,
                end_date=interval_end,
                updated_at_utc=_optional_str(manifest.get("updated_at_utc")),
            )
        )
    return _build_selection(
        source_system="sp_api_reports",
        report_type=report_type,
        start_date=start_date,
        end_date=end_date,
        candidates=candidates,
    )


def select_ads_period_raw_files(
    *,
    sampling_root: str | Path,
    profile_id: str,
    report_type_id: str,
    start_date: date,
    end_date: date,
) -> PeriodRawFileSelection:
    _validate_window(start_date=start_date, end_date=end_date)
    manifests_dir = Path(sampling_root) / "ads_report_requests"
    candidates: list[PeriodRawFile] = []
    for manifest in _iter_json_objects(manifests_dir):
        if str(manifest.get("profile_id") or "") != profile_id:
            continue
        if str(manifest.get("report_type_id") or "") != report_type_id:
            continue
        if str(manifest.get("processing_status") or "").upper() != "COMPLETED":
            continue
        if str(manifest.get("download_status") or "").upper() != "DOWNLOADED":
            continue
        raw_file_path = str(manifest.get("raw_file_path") or "")
        if not raw_file_path or not Path(raw_file_path).is_file():
            continue
        interval_start = _as_date(manifest.get("data_start_date"))
        interval_end = _as_date(manifest.get("data_end_date"))
        if interval_start is None or interval_end is None or interval_end < interval_start:
            continue
        if not _overlaps(
            interval_start,
            interval_end,
            target_start=start_date,
            target_end=end_date,
        ):
            continue
        candidates.append(
            PeriodRawFile(
                report_id=str(manifest.get("ads_report_id") or Path(raw_file_path).stem),
                raw_file_path=raw_file_path,
                start_date=interval_start,
                end_date=interval_end,
                updated_at_utc=_optional_str(manifest.get("updated_at_utc")),
            )
        )
    return _build_selection(
        source_system="amazon_ads",
        report_type=report_type_id,
        start_date=start_date,
        end_date=end_date,
        candidates=candidates,
    )


def _build_selection(
    *,
    source_system: str,
    report_type: str,
    start_date: date,
    end_date: date,
    candidates: Iterable[PeriodRawFile],
) -> PeriodRawFileSelection:
    deduped: dict[tuple[date, date], PeriodRawFile] = {}
    for item in candidates:
        key = (item.start_date, item.end_date)
        current = deduped.get(key)
        if current is None or _selection_rank(item) > _selection_rank(current):
            deduped[key] = item
    files = tuple(
        sorted(
            deduped.values(),
            key=lambda item: (item.start_date, item.end_date, item.report_id),
        )
    )
    missing_ranges = _missing_date_ranges(
        ((item.start_date, item.end_date) for item in files),
        target_start=start_date,
        target_end=end_date,
    )
    return PeriodRawFileSelection(
        source_system=source_system,
        report_type=report_type,
        target_start_date=start_date,
        target_end_date=end_date,
        files=files,
        coverage_complete=not missing_ranges,
        missing_ranges=missing_ranges,
    )


def _selection_rank(item: PeriodRawFile) -> tuple[datetime, str]:
    updated = _as_datetime(item.updated_at_utc) or datetime.min.replace(tzinfo=UTC)
    return updated, item.report_id


def _missing_date_ranges(
    intervals: Iterable[tuple[date, date]],
    *,
    target_start: date,
    target_end: date,
) -> tuple[tuple[date, date], ...]:
    clipped: list[tuple[date, date]] = []
    for start, end in intervals:
        clipped_start = max(start, target_start)
        clipped_end = min(end, target_end)
        if clipped_end >= clipped_start:
            clipped.append((clipped_start, clipped_end))
    clipped.sort()

    missing: list[tuple[date, date]] = []
    cursor = target_start
    for start, end in clipped:
        if end < cursor:
            continue
        if start > cursor:
            missing.append((cursor, start - timedelta(days=1)))
        cursor = max(cursor, end + timedelta(days=1))
        if cursor > target_end:
            break
    if cursor <= target_end:
        missing.append((cursor, target_end))
    return tuple(missing)


def _overlaps(start: date, end: date, *, target_start: date, target_end: date) -> bool:
    return start <= target_end and end >= target_start


def _iter_json_objects(directory: Path) -> Iterable[dict[str, Any]]:
    if not directory.exists():
        return ()
    payloads: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return tuple(payloads)


def _as_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        result = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            result = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if result.tzinfo is None:
        return result.replace(tzinfo=UTC)
    return result.astimezone(UTC)


def _as_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _validate_window(*, start_date: date, end_date: date) -> None:
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")


__all__ = [
    "PeriodRawFile",
    "PeriodRawFileSelection",
    "select_ads_period_raw_files",
    "select_sp_api_period_raw_files",
]
