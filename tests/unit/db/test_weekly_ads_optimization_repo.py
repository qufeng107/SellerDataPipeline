from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from seller_data_pipeline.db.repositories.weekly_ads_optimization_repo import (
    WeeklyAdsOptimizationRepo,
)


class FakeCursor:
    def __init__(self, rows: list[tuple[Any, ...]] | None = None) -> None:
        self.rows = rows or []
        self.description = [("value",)]
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self.closed = False

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self.executed.append((sql, params))

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.rows

    def fetchone(self) -> tuple[Any, ...] | None:
        return self.rows[0] if self.rows else None

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> FakeCursor:
        return self._cursor


def test_fetch_campaign_daily_filters_profile_and_week() -> None:
    cursor = FakeCursor(rows=[(Decimal("1.00"),)])
    cursor.description = [("cost",)]
    repo = WeeklyAdsOptimizationRepo(FakeConnection(cursor))

    rows = repo.fetch_campaign_daily_rows(
        marketplace_id="ATVPDKIKX0DER",
        profile_id="3917953989967300",
        start_date=date(2026, 5, 11),
        end_date=date(2026, 5, 17),
    )

    sql, params = cursor.executed[0]
    assert "amazon_ads_sp_campaign_daily" in sql
    assert "[profile_id] = ?" in sql
    assert "[report_date] >= ?" in sql
    assert params == (
        "ATVPDKIKX0DER",
        "3917953989967300",
        date(2026, 5, 11),
        date(2026, 5, 17),
    )
    assert rows == [{"cost": Decimal("1.00")}]
    assert cursor.closed is True


def test_fetch_search_term_daily_selects_search_term_fields() -> None:
    cursor = FakeCursor(rows=[])
    repo = WeeklyAdsOptimizationRepo(FakeConnection(cursor))

    repo.fetch_search_term_daily_rows(
        marketplace_id="ATVPDKIKX0DER",
        profile_id=None,
        start_date=date(2026, 5, 11),
        end_date=date(2026, 5, 17),
    )

    sql, params = cursor.executed[0]
    assert "amazon_ads_sp_search_term_daily" in sql
    assert "[search_term]" in sql
    assert "[profile_id] = ?" not in sql
    assert params == ("ATVPDKIKX0DER", date(2026, 5, 11), date(2026, 5, 17))


def test_fetch_targeting_daily_selects_targeting_fields() -> None:
    cursor = FakeCursor(rows=[])
    repo = WeeklyAdsOptimizationRepo(FakeConnection(cursor))

    repo.fetch_targeting_daily_rows(
        marketplace_id="ATVPDKIKX0DER",
        profile_id="3917953989967300",
        start_date=date(2026, 5, 11),
        end_date=date(2026, 5, 17),
    )

    sql, _ = cursor.executed[0]
    assert "amazon_ads_sp_targeting_daily" in sql
    assert "[keyword]" in sql
    assert "[targeting]" in sql


def test_fetch_advertised_product_daily_selects_sku_asin_fields() -> None:
    cursor = FakeCursor(rows=[])
    repo = WeeklyAdsOptimizationRepo(FakeConnection(cursor))

    repo.fetch_advertised_product_daily_rows(
        marketplace_id="ATVPDKIKX0DER",
        profile_id="3917953989967300",
        start_date=date(2026, 5, 11),
        end_date=date(2026, 5, 17),
    )

    sql, _ = cursor.executed[0]
    assert "amazon_ads_sp_advertised_product_daily" in sql
    assert "[advertised_sku]" in sql
    assert "[advertised_asin]" in sql


def test_fetch_settlement_advertising_summary_uses_posted_date_logic() -> None:
    cursor = FakeCursor(rows=[(Decimal("-10.00"), 5, "USD")])
    cursor.description = [
        ("settlement_advertising_fee",),
        ("settlement_row_count",),
        ("currency",),
    ]
    repo = WeeklyAdsOptimizationRepo(FakeConnection(cursor))

    result = repo.fetch_settlement_advertising_summary(
        marketplace_id="ATVPDKIKX0DER",
        start_date=date(2026, 5, 11),
        end_date=date(2026, 5, 17),
    )

    sql, params = cursor.executed[0]
    assert "amazon_settlement_transaction" in sql
    assert "posted_date_time_raw" in sql
    assert "advertising_cost" in sql
    assert params == ("ATVPDKIKX0DER", date(2026, 5, 11), date(2026, 5, 17))
    assert result["settlement_advertising_fee"] == Decimal("-10.00")
