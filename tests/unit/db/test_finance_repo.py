from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from seller_data_pipeline.db.repositories.finance_repo import (
    FinanceRepo,
    one_row_to_dict,
    rows_to_dicts,
)


class FakeCursor:
    def __init__(self, rows: list[tuple[Any, ...]] | None = None) -> None:
        self.rows = rows or []
        self.fetchone_rows = list(self.rows)
        self.description = [("id",), ("amount",)]
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


def test_rows_to_dicts() -> None:
    cursor = FakeCursor(rows=[(1, Decimal("2.50"))])

    assert rows_to_dicts(cursor) == [{"id": 1, "amount": Decimal("2.50")}]


def test_one_row_to_dict_returns_empty_when_no_rows() -> None:
    cursor = FakeCursor(rows=[])

    assert one_row_to_dict(cursor) == {}


def test_fetch_settlement_profit_rows_filters_marketplace_and_period() -> None:
    cursor = FakeCursor(rows=[])
    cursor.description = [("id",), ("marketplace_id",)]
    repo = FinanceRepo(FakeConnection(cursor))

    repo.fetch_settlement_profit_rows(
        marketplace_id="ATVPDKIKX0DER",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 7),
    )

    sql, params = cursor.executed[0]
    assert "amazon_settlement_transaction" in sql
    assert "TRY_CONVERT(date" in sql
    assert ", 104)" in sql
    assert "UPPER(NULLIF([currency], '')) = ?" in sql
    assert "[is_settlement_summary] = 0" in sql
    assert params == ("ATVPDKIKX0DER", "USD", date(2026, 5, 1), date(2026, 5, 7))
    assert cursor.closed is True


def test_fetch_sku_cost_rows_uses_effective_overlap() -> None:
    cursor = FakeCursor(rows=[])
    cursor.description = [("marketplace_id",)]
    repo = FinanceRepo(FakeConnection(cursor))

    repo.fetch_sku_cost_rows(
        marketplace_id="ATVPDKIKX0DER",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 7),
    )

    sql, params = cursor.executed[0]
    assert "amazon_sku_cost" in sql
    assert "[effective_from] <= ?" in sql
    assert "[effective_to] IS NULL OR [effective_to] >= ?" in sql
    assert params == ("ATVPDKIKX0DER", date(2026, 5, 7), date(2026, 5, 1))
