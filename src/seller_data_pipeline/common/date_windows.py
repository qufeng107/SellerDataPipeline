from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class DateWindow:
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("DateWindow.end must be >= DateWindow.start")


def recent_days_window(today: date, days: int) -> DateWindow:
    if days <= 0:
        raise ValueError("days must be positive")
    return DateWindow(start=today - timedelta(days=days), end=today)


def previous_complete_week(today: date) -> DateWindow:
    """Return last complete Monday-Sunday week before today."""
    current_week_monday = today - timedelta(days=today.weekday())
    start = current_week_monday - timedelta(days=7)
    end = current_week_monday - timedelta(days=1)
    return DateWindow(start=start, end=end)


def stable_profit_week(today: date) -> DateWindow:
    """Return the complete Monday-Sunday week before the previous complete week."""
    current_week_monday = today - timedelta(days=today.weekday())
    start = current_week_monday - timedelta(days=14)
    end = current_week_monday - timedelta(days=8)
    return DateWindow(start=start, end=end)


def chunk_inclusive_date_range(
    *,
    start: date,
    end: date,
    chunk_days: int,
) -> tuple[DateWindow, ...]:
    """Split an inclusive date range into contiguous inclusive DateWindow chunks.

    DateWindow.end is inclusive for this helper. This is intended for human-facing
    backfill commands where users think in closed calendar ranges such as
    2026-03-01..2026-03-31.
    """

    if chunk_days <= 0:
        raise ValueError("chunk_days must be positive")
    if end < start:
        raise ValueError("end must be on or after start")

    chunks: list[DateWindow] = []
    current_start = start
    while current_start <= end:
        current_end = min(current_start + timedelta(days=chunk_days - 1), end)
        chunks.append(DateWindow(start=current_start, end=current_end))
        current_start = current_end + timedelta(days=1)
    return tuple(chunks)


def inclusive_date_range_to_exclusive_end_datetime(
    *,
    start: date,
    end: date,
) -> tuple[date, date]:
    """Return the calendar start and exclusive end date for SP-API dateTime reports."""

    if end < start:
        raise ValueError("end must be on or after start")
    return start, end + timedelta(days=1)
