from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from seller_data_pipeline.db.repositories.weekly_business_review_repo import (
    WeeklyBusinessReviewRepo,
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

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> FakeCursor:
        return self._cursor


def test_fetch_sales_traffic_daily_rows_filters_week() -> None:
    cursor = FakeCursor(rows=[])
    cursor.description = [("report_date",)]
    repo = WeeklyBusinessReviewRepo(FakeConnection(cursor))

    repo.fetch_sales_traffic_daily_rows(
        marketplace_id="ATVPDKIKX0DER",
        start_date=date(2026, 4, 6),
        end_date=date(2026, 4, 12),
    )

    sql, params = cursor.executed[0]
    assert "amazon_sales_traffic_daily" in sql
    assert "[report_date] >= ?" in sql
    assert params == ("ATVPDKIKX0DER", date(2026, 4, 6), date(2026, 4, 12))
    assert cursor.closed is True


def test_fetch_order_item_rows_parses_purchase_date_and_filters_cancelled() -> None:
    cursor = FakeCursor(rows=[])
    repo = WeeklyBusinessReviewRepo(FakeConnection(cursor))

    repo.fetch_order_item_rows(
        marketplace_id="ATVPDKIKX0DER",
        start_date=date(2026, 4, 6),
        end_date=date(2026, 4, 12),
    )

    sql, params = cursor.executed[0]
    assert "amazon_order_item" in sql
    assert "TRY_CONVERT(date" in sql
    assert "NOT IN ('Cancelled', 'Canceled')" in sql
    assert params == ("ATVPDKIKX0DER", date(2026, 4, 6), date(2026, 4, 12))


def test_fetch_ads_campaign_daily_rows_filters_profile_when_supplied() -> None:
    cursor = FakeCursor(rows=[(Decimal("1.00"),)])
    cursor.description = [("cost",)]
    repo = WeeklyBusinessReviewRepo(FakeConnection(cursor))

    repo.fetch_ads_campaign_daily_rows(
        marketplace_id="ATVPDKIKX0DER",
        profile_id="3917953989967300",
        start_date=date(2026, 4, 6),
        end_date=date(2026, 4, 12),
    )

    sql, params = cursor.executed[0]
    assert "amazon_ads_sp_campaign_daily" in sql
    assert "[profile_id] = ?" in sql
    assert params == (
        "ATVPDKIKX0DER",
        "3917953989967300",
        date(2026, 4, 6),
        date(2026, 4, 12),
    )


def test_fetch_latest_inventory_rows_uses_latest_snapshot_cte() -> None:
    cursor = FakeCursor(rows=[])
    repo = WeeklyBusinessReviewRepo(FakeConnection(cursor))

    repo.fetch_latest_inventory_rows(
        marketplace_id="ATVPDKIKX0DER",
        as_of_date=date(2026, 4, 12),
    )

    sql, params = cursor.executed[0]
    assert "MAX([snapshot_date])" in sql
    assert "amazon_inventory_daily" in sql
    assert params == ("ATVPDKIKX0DER", date(2026, 4, 12), "ATVPDKIKX0DER")


def test_fetch_settlement_preview_rows_uses_posted_date_logic() -> None:
    cursor = FakeCursor(rows=[])
    repo = WeeklyBusinessReviewRepo(FakeConnection(cursor))

    repo.fetch_settlement_preview_rows(
        marketplace_id="ATVPDKIKX0DER",
        start_date=date(2026, 4, 6),
        end_date=date(2026, 4, 12),
    )

    sql, params = cursor.executed[0]
    assert "amazon_settlement_transaction" in sql
    assert "[is_settlement_summary] = 0" in sql
    assert "posted_date_time_raw" in sql
    assert ", 104)" in sql
    assert "UPPER(NULLIF([currency], '')) = ?" in sql
    assert params == ("ATVPDKIKX0DER", "USD", date(2026, 4, 6), date(2026, 4, 12))
