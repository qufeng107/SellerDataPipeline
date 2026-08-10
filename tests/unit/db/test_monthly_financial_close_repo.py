from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from seller_data_pipeline.db.repositories.monthly_financial_close_repo import (
    MonthlyFinancialCloseRepo,
)


class FakeCursor:
    def __init__(self, rows: list[tuple[Any, ...]] | None = None) -> None:
        self.rows = rows or []
        self.fetchone_rows = list(self.rows)
        self.description = [("value",)]
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self.closed = False

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self.executed.append((sql, params))

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.rows

    def fetchone(self) -> tuple[Any, ...] | None:
        if not self.fetchone_rows:
            return None
        return self.fetchone_rows.pop(0)

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> FakeCursor:
        return self._cursor


def test_fetch_settlement_profit_rows_uses_monthly_close_filters() -> None:
    cursor = FakeCursor(rows=[])
    cursor.description = [("id",), ("marketplace_id",)]
    repo = MonthlyFinancialCloseRepo(FakeConnection(cursor))

    repo.fetch_settlement_profit_rows(
        marketplace_id="ATVPDKIKX0DER",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
    )

    sql, params = cursor.executed[0]
    assert "amazon_settlement_transaction" in sql
    assert "TRY_CONVERT(date" in sql
    assert ", 104)" in sql
    assert "UPPER(NULLIF([currency], '')) = ?" in sql
    assert "[is_settlement_summary] = 0" in sql
    assert "[source_raw_file_path]" in sql
    assert params == ("ATVPDKIKX0DER", "USD", date(2026, 3, 1), date(2026, 3, 31))
    assert cursor.closed is True


def test_fetch_ads_period_summary_filters_profile_when_supplied() -> None:
    cursor = FakeCursor(rows=[(Decimal("1.00"),)])
    cursor.description = [("ads_cost",)]
    repo = MonthlyFinancialCloseRepo(FakeConnection(cursor))

    repo.fetch_ads_period_summary(
        marketplace_id="ATVPDKIKX0DER",
        profile_id="3917953989967300",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
    )

    sql, params = cursor.executed[0]
    assert "amazon_ads_sp_campaign_daily" in sql
    assert "[profile_id] = ?" in sql
    assert params == (
        "ATVPDKIKX0DER",
        "3917953989967300",
        date(2026, 3, 1),
        date(2026, 3, 31),
    )


def test_fetch_ads_period_summary_allows_missing_profile() -> None:
    cursor = FakeCursor(rows=[])
    repo = MonthlyFinancialCloseRepo(FakeConnection(cursor))

    repo.fetch_ads_period_summary(
        marketplace_id="ATVPDKIKX0DER",
        profile_id=None,
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
    )

    sql, params = cursor.executed[0]
    assert "[profile_id] = ?" not in sql
    assert params == ("ATVPDKIKX0DER", date(2026, 3, 1), date(2026, 3, 31))


def test_fetch_coupon_period_summary_uses_overlap_window() -> None:
    cursor = FakeCursor(rows=[])
    repo = MonthlyFinancialCloseRepo(FakeConnection(cursor))

    repo.fetch_coupon_period_summary(
        marketplace_id="ATVPDKIKX0DER",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
    )

    sql, params = cursor.executed[0]
    assert "amazon_coupon_performance" in sql
    assert "[start_date] <= ?" in sql
    assert "[end_date] >= ?" in sql
    assert params == ("ATVPDKIKX0DER", date(2026, 3, 31), date(2026, 3, 1))


def test_fetch_fba_reimbursement_period_summary_uses_approval_date() -> None:
    cursor = FakeCursor(rows=[])
    repo = MonthlyFinancialCloseRepo(FakeConnection(cursor))

    repo.fetch_fba_reimbursement_period_summary(
        marketplace_id="ATVPDKIKX0DER",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
    )

    sql, params = cursor.executed[0]
    assert "amazon_fba_reimbursement" in sql
    assert "approval_date" in sql
    assert params == ("ATVPDKIKX0DER", date(2026, 3, 1), date(2026, 3, 31))


def test_fetch_inventory_cost_identity_rows_is_historical_and_preserves_ambiguity() -> None:
    cursor = FakeCursor(rows=[])
    cursor.description = [
        ("marketplace_id",),
        ("fnsku",),
        ("seller_sku",),
        ("asin",),
    ]
    repo = MonthlyFinancialCloseRepo(FakeConnection(cursor))

    repo.fetch_inventory_cost_identity_rows(
        marketplace_id="ATVPDKIKX0DER",
        as_of_date=date(2026, 7, 31),
    )

    sql, params = cursor.executed[0]
    assert "amazon_inventory_daily" in sql
    assert "SELECT DISTINCT" in sql
    assert "[snapshot_date] <= ?" in sql
    assert "[fnsku]" in sql
    assert "[seller_sku]" in sql
    assert params == ("ATVPDKIKX0DER", date(2026, 7, 31))
    assert cursor.closed is True
