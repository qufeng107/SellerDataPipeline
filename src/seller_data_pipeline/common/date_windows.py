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
