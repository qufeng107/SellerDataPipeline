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
    """Return the latest complete Saturday-Friday week before today.

    Weekly management reports use a Saturday-Friday period and are normally
    generated on Monday, leaving a small buffer for late Amazon source data.
    """

    # Python weekday: Monday=0 ... Friday=4, Saturday=5, Sunday=6.
    days_since_saturday = (today.weekday() - 5) % 7
    current_period_start = today - timedelta(days=days_since_saturday)
    start = current_period_start - timedelta(days=7)
    end = current_period_start - timedelta(days=1)
    return DateWindow(start=start, end=end)


def stable_profit_week(today: date) -> DateWindow:
    """Return the Saturday-Friday week before the previous complete week."""

    quick = previous_complete_week(today)
    return DateWindow(start=quick.start - timedelta(days=7), end=quick.end - timedelta(days=7))


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
