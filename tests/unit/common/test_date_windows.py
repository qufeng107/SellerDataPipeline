from datetime import date

from seller_data_pipeline.common.date_windows import (
    chunk_inclusive_date_range,
    previous_complete_week,
    stable_profit_week,
)


def test_previous_complete_week_uses_saturday_friday_for_monday_scheduler() -> None:
    window = previous_complete_week(date(2026, 5, 11))
    assert window.start == date(2026, 5, 2)
    assert window.end == date(2026, 5, 8)


def test_stable_profit_week_uses_previous_saturday_friday() -> None:
    window = stable_profit_week(date(2026, 5, 11))
    assert window.start == date(2026, 4, 25)
    assert window.end == date(2026, 5, 1)


def test_chunk_inclusive_date_range_splits_closed_range() -> None:
    windows = chunk_inclusive_date_range(
        start=date(2026, 3, 1),
        end=date(2026, 3, 31),
        chunk_days=14,
    )

    assert [(window.start, window.end) for window in windows] == [
        (date(2026, 3, 1), date(2026, 3, 14)),
        (date(2026, 3, 15), date(2026, 3, 28)),
        (date(2026, 3, 29), date(2026, 3, 31)),
    ]
