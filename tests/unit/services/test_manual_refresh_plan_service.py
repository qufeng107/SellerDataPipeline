from __future__ import annotations

from seller_data_pipeline.services.manual_refresh_plan_service import ManualRefreshPlanService


def test_core_rolling_submit_plan_contains_expected_sources() -> None:
    commands = ManualRefreshPlanService().build_commands(
        plan="core_rolling",
        phase="submit",
        marketplace_id="ATVPDKIKX0DER",
        profile_id="123",
        target_start_date="2026-03-01",
    )

    printable = "\n".join(command.printable() for command in commands)

    assert len(commands) == 5
    assert "GET_SALES_AND_TRAFFIC_REPORT" in printable
    assert "GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL" in printable
    assert "GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA" in printable
    assert "run_ads_sampling_plan.py --days 14 --profile-id 123 --force" in printable
    assert "GET_PROMOTION_PERFORMANCE_REPORT" in printable
    assert "GET_COUPON_PERFORMANCE_REPORT" in printable


def test_weekly_full_ingest_extends_core_ingestion() -> None:
    commands = ManualRefreshPlanService().build_commands(
        plan="weekly_full",
        phase="ingest",
        marketplace_id="ATVPDKIKX0DER",
        profile_id="123",
        target_start_date="2026-03-01",
    )

    printable = "\n".join(command.printable() for command in commands)

    assert len(commands) == 10
    assert "ingest_sales_traffic_report.py" in printable
    assert "ingest_orders_report.py" in printable
    assert "ingest_ads_reports.py" in printable
    assert "ingest_settlement_report.py" in printable
    assert "ingest_fba_reimbursements_report.py" in printable
    assert "ingest_inventory_ledger_reports.py" in printable
    assert "ingest_listing_snapshot.py" in printable
    assert "ingest_fba_fee_preview_report.py" in printable
    assert printable.count("--execute") == 10


def test_audit_plan_uses_target_start_date() -> None:
    commands = ManualRefreshPlanService().build_commands(
        plan="core_rolling",
        phase="audit",
        marketplace_id="ATVPDKIKX0DER",
        profile_id=None,
        target_start_date="2026-04-01",
    )

    assert len(commands) == 1
    assert commands[0].argv == (
        "scripts/audit_data_coverage.py",
        "--marketplace-id",
        "ATVPDKIKX0DER",
        "--target-start-date",
        "2026-04-01",
    )


def test_dry_run_does_not_execute_commands() -> None:
    result = ManualRefreshPlanService().run(
        plan="core_rolling",
        phase="collect",
        marketplace_id="ATVPDKIKX0DER",
        profile_id=None,
        target_start_date="2026-03-01",
        execute=False,
    )

    assert result.executed is False
    assert result.return_codes == ()
    assert len(result.commands) == 2
