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
    assert "weekly_business_review_2026-05-16_2026-05-22.json" in printable
    assert "weekly_ads_optimization_2026-05-16_2026-05-22.json" in printable


def test_weekly_report_delivery_commands_pass_email_to_override() -> None:
    commands = AutomationScheduleService().build_commands(
        workflow="weekly",
        phase="report_delivery",
        marketplace_id="ATVPDKIKX0DER",
        profile_id="3917953989967300",
        reference_date=date(2026, 5, 25),
        send_email=True,
        force_resend=True,
        email_to=("feng@cuidena.cn",),
    )

    send_commands = [
        command for command in commands if command.argv[0] == "scripts/send_report_email.py"
    ]
    assert len(send_commands) == 2
    for command in send_commands:
        assert "--execute" in command.argv
        assert "--force-resend" in command.argv
        assert "--to" in command.argv
        assert "feng@cuidena.cn" in command.argv


def test_monthly_report_delivery_commands_pass_email_to_override() -> None:
    commands = AutomationScheduleService().build_commands(
        workflow="monthly",
        phase="report_delivery",
        marketplace_id="ATVPDKIKX0DER",
        profile_id="3917953989967300",
        reference_date=date(2026, 5, 3),
        send_email=True,
        email_to=("feng@cuidena.cn", "ops@example.com"),
    )

    printable = "\n".join(command.printable() for command in commands)
    assert "--to feng@cuidena.cn" in printable
    assert "--to ops@example.com" in printable


def test_run_records_command_callbacks(monkeypatch) -> None:
    import subprocess
    from datetime import datetime

    service = AutomationScheduleService()
    command = service.build_commands(
        workflow="weekly",
        phase="submit",
        marketplace_id="ATVPDKIKX0DER",
        profile_id=None,
        reference_date=date(2026, 5, 25),
    )[0]
    started: list[tuple[int, str]] = []
    finished: list[tuple[object, int | None]] = []

    def fake_run(argv, check=False):
        assert check is False
        return subprocess.CompletedProcess(argv, 0)

    def on_start(index, command, started_at):
        assert isinstance(started_at, datetime)
        started.append((index, command.label))
        return {"id": index}

    def on_finish(handle, exit_code, finished_at):
        assert isinstance(finished_at, datetime)
        finished.append((handle, exit_code))

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = service.run(
        workflow="weekly",
        phase="submit",
        artifact_scope="weekly:scope",
        commands=(command,),
        execute=True,
        command_started=on_start,
        command_finished=on_finish,
    )

    assert result.return_codes == (0,)
    assert len(result.command_executions) == 1
    assert result.command_executions[0].duration_ms is not None
    assert started == [(1, command.label)]
    assert finished == [({"id": 1}, 0)]
