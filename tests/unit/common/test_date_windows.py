from datetime import date

from seller_data_pipeline.common.date_windows import previous_complete_week, stable_profit_week


def test_previous_complete_week_for_monday() -> None:
    window = previous_complete_week(date(2026, 5, 11))
    assert window.start == date(2026, 5, 4)
    assert window.end == date(2026, 5, 10)


def test_stable_profit_week_for_monday() -> None:
    window = stable_profit_week(date(2026, 5, 11))
    assert window.start == date(2026, 4, 27)
    assert window.end == date(2026, 5, 3)
