from __future__ import annotations

from datetime import date
from typing import Any

from seller_data_pipeline.db.repositories.data_coverage_repo import (
    CoverageSourceSpec,
    DataCoverageRepo,
)


class FakeCursor:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows
        self.description = [("row_count",)]
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


def test_fetch_core_coverage_rows_uses_spec_and_target_window_params() -> None:
    cursor = FakeCursor(rows=[(0,)])
    repo = DataCoverageRepo(FakeConnection(cursor))
    specs = (
        CoverageSourceSpec(
            data_domain="Orders",
            source_table="amazon_order_item",
            business_date_expression="[purchase_date_raw]",
            business_date_semantics="purchase_date",
            entity_expression="[seller_sku]",
        ),
    )

    rows = repo.fetch_core_coverage_rows(
        marketplace_id="ATVPDKIKX0DER",
        target_start_date=date(2026, 1, 1),
        target_end_date=date(2026, 5, 18),
        specs=specs,
    )

    assert rows[0]["data_domain"] == "Orders"
    sql, params = cursor.executed[0]
    assert "amazon_order_item" in sql
    assert "[marketplace_id] = ?" in sql
    assert "[seller_sku]" in sql
    assert params == (
        "ATVPDKIKX0DER",
        date(2026, 1, 1),
        date(2026, 5, 18),
        date(2026, 1, 1),
        date(2026, 5, 18),
        date(2026, 1, 1),
        date(2026, 5, 18),
    )
    assert cursor.closed is True


def test_fetch_report_request_coverage_rows_groups_by_source_and_report_type() -> None:
    cursor = FakeCursor(rows=[])
    repo = DataCoverageRepo(FakeConnection(cursor))

    repo.fetch_report_request_coverage_rows(
        marketplace_id="ATVPDKIKX0DER",
        target_start_date=date(2026, 1, 1),
        target_end_date=date(2026, 5, 18),
    )

    sql, params = cursor.executed[0]
    assert "amazon_report_request" in sql
    assert "GROUP BY [source_system], [report_type]" in sql
    assert params == (date(2026, 1, 1), date(2026, 5, 18), "ATVPDKIKX0DER")
