from __future__ import annotations

from datetime import date

from seller_data_pipeline.services.automation_schedule_service import (
    AutomationScheduleService,
    monthly_automation_window,
    weekly_automation_window,
)


def test_weekly_automation_window_uses_saturday_to_friday_and_wednesday_request_buffer() -> None:
    window = weekly_automation_window(date(2026, 5, 25))  # Monday scheduler day.

    assert window.stats_start == date(2026, 5, 16)
    assert window.stats_end == date(2026, 5, 22)
    assert window.request_start == date(2026, 5, 13)
    assert window.request_end == date(2026, 5, 22)
    assert window.period_key == "2026-05-16_2026-05-22"


def test_weekly_automation_window_rejects_manual_non_saturday_start() -> None:
    try:
        weekly_automation_window(date(2026, 5, 25), week_start=date(2026, 5, 18))
    except ValueError as exc:
        assert "Saturday" in str(exc)
    else:
        raise AssertionError("Expected non-Saturday automation week_start to fail")


def test_monthly_automation_window_defaults_to_previous_month() -> None:
    window = monthly_automation_window(date(2026, 5, 3))

    assert window.month == "2026-04"
    assert window.start == date(2026, 4, 1)
    assert window.end == date(2026, 4, 30)


def test_build_weekly_submit_commands_include_buffered_range() -> None:
    commands = AutomationScheduleService().build_commands(
        workflow="weekly",
        phase="submit",
        marketplace_id="ATVPDKIKX0DER",
        profile_id="3917953989967300",
        reference_date=date(2026, 5, 25),
    )

    printable = "\n".join(command.printable() for command in commands)
    assert "--start-date 2026-05-13 --end-date 2026-05-22" in printable
    assert "GET_SALES_AND_TRAFFIC_REPORT" in printable
    assert "scripts/backfill_ads_reports.py" in printable


def test_weekly_report_delivery_commands_use_date_stamped_report_json_paths() -> None:
    commands = AutomationScheduleService().build_commands(
        workflow="weekly",
        phase="report_delivery",
        marketplace_id="ATVPDKIKX0DER",
        profile_id="3917953989967300",
        reference_date=date(2026, 5, 25),
    )

    printable = "\n".join(command.printable() for command in commands)
    assert (
        "weekly_business_review_2026-05-16_2026-05-22.json"
        in printable
    )
    assert (
        "weekly_ads_optimization_2026-05-16_2026-05-22.json"
        in printable
    )
