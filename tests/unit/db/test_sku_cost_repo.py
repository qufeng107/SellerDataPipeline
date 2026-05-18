from __future__ import annotations

from datetime import date
from decimal import Decimal

from seller_data_pipeline.db.repositories.sku_cost_repo import (
    INSERT_SKU_COST_SQL,
    UPDATE_SKU_COST_SQL,
    SkuCandidateRecord,
    SkuCostRecord,
    SkuCostRepo,
    SkuCostWriteRecord,
    _db_decimal,
)


class FakeCursor:
    def __init__(self, rows: list[tuple] | None = None, one: tuple | None = None) -> None:
        self.rows = rows or []
        self.one = one
        self.executed: list[tuple[str, tuple]] = []
        self.rowcount = 0
        self.closed = False

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.executed.append((sql, params))

    def fetchall(self) -> list[tuple]:
        return self.rows

    def fetchone(self) -> tuple | None:
        return self.one

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self, cursors: list[FakeCursor]) -> None:
        self.cursors = cursors
        self.cursor_calls = 0
        self.committed = False

    def cursor(self) -> FakeCursor:
        cursor = self.cursors[self.cursor_calls]
        self.cursor_calls += 1
        return cursor

    def commit(self) -> None:
        self.committed = True


def test_fetch_sku_candidates_maps_rows_and_uses_marketplace_for_each_source() -> None:
    cursor = FakeCursor(
        rows=[
            (
                "ATVPDKIKX0DER",
                "SKU-A",
                "ASIN1",
                "Neck Wallet",
                "listing,orders",
                date(2026, 5, 10),
            )
        ]
    )
    repo = SkuCostRepo(FakeConnection([cursor]))

    rows = repo.fetch_sku_candidates(marketplace_id="ATVPDKIKX0DER")

    assert rows == [
        SkuCandidateRecord(
            marketplace_id="ATVPDKIKX0DER",
            seller_sku="SKU-A",
            asin="ASIN1",
            product_name="Neck Wallet",
            sku_sources="listing,orders",
            latest_source_date=date(2026, 5, 10),
        )
    ]
    assert cursor.executed[0][1] == ("ATVPDKIKX0DER",) * 4
    assert "amazon_listing_snapshot" in cursor.executed[0][0]
    assert "amazon_settlement_transaction" in cursor.executed[0][0]
    assert cursor.closed is True


def test_fetch_latest_sku_costs_maps_decimal_fields_by_sku() -> None:
    cursor = FakeCursor(
        rows=[
            (
                "ATVPDKIKX0DER",
                "SKU-A",
                "ASIN1",
                Decimal("2.1000"),
                Decimal("0.4500"),
                Decimal("0.1200"),
                Decimal("0.0000"),
                "USD",
                date(2026, 1, 1),
                None,
                "initial",
                "2026-05-18 00:00:00",
            )
        ]
    )
    repo = SkuCostRepo(FakeConnection([cursor]))

    rows = repo.fetch_latest_sku_costs(marketplace_id="ATVPDKIKX0DER")

    assert rows["SKU-A"] == SkuCostRecord(
        marketplace_id="ATVPDKIKX0DER",
        seller_sku="SKU-A",
        asin="ASIN1",
        product_cost=Decimal("2.1000"),
        first_mile_cost=Decimal("0.4500"),
        packaging_cost=Decimal("0.1200"),
        other_unit_cost=Decimal("0.0000"),
        currency="USD",
        effective_from=date(2026, 1, 1),
        remark="initial",
        updated_at="2026-05-18 00:00:00",
    )


def test_sku_cost_exists_returns_true_when_count_positive() -> None:
    cursor = FakeCursor(one=(1,))
    repo = SkuCostRepo(FakeConnection([cursor]))

    assert repo.sku_cost_exists(
        marketplace_id="ATVPDKIKX0DER",
        seller_sku="SKU-A",
        effective_from=date(2026, 1, 1),
    ) is True
    assert cursor.executed[0][1] == ("ATVPDKIKX0DER", "SKU-A", date(2026, 1, 1))


def test_insert_sku_cost_uses_expected_sql_and_decimal_params() -> None:
    cursor = FakeCursor()
    repo = SkuCostRepo(FakeConnection([cursor]))
    record = SkuCostWriteRecord(
        marketplace_id="ATVPDKIKX0DER",
        seller_sku="SKU-A",
        asin="ASIN1",
        product_cost=Decimal("2.1"),
        first_mile_cost=Decimal("0.45"),
        packaging_cost=Decimal("0.12"),
        other_unit_cost=Decimal("0"),
        currency="USD",
        effective_from=date(2026, 1, 1),
        remark="initial",
    )

    repo.insert_sku_cost(record)

    sql, params = cursor.executed[0]
    assert sql == INSERT_SKU_COST_SQL
    assert params[0:3] == ("ATVPDKIKX0DER", "SKU-A", "ASIN1")
    assert params[3:7] == ("2.1000", "0.4500", "0.1200", "0.0000")


def test_update_sku_cost_uses_key_in_where_params() -> None:
    cursor = FakeCursor()
    repo = SkuCostRepo(FakeConnection([cursor]))
    record = SkuCostWriteRecord(
        marketplace_id="ATVPDKIKX0DER",
        seller_sku="SKU-A",
        asin="ASIN1",
        product_cost=Decimal("2.1"),
        first_mile_cost=Decimal("0.45"),
        packaging_cost=Decimal("0.12"),
        other_unit_cost=Decimal("0"),
        currency="USD",
        effective_from=date(2026, 1, 1),
        remark="updated",
    )

    repo.update_sku_cost(record)

    sql, params = cursor.executed[0]
    assert sql == UPDATE_SKU_COST_SQL
    assert params[-3:] == ("ATVPDKIKX0DER", "SKU-A", date(2026, 1, 1))


def test_close_previous_open_cost_closes_only_older_open_rows() -> None:
    cursor = FakeCursor()
    cursor.rowcount = 1
    repo = SkuCostRepo(FakeConnection([cursor]))

    rows = repo.close_previous_open_cost(
        marketplace_id="ATVPDKIKX0DER",
        seller_sku="SKU-A",
        new_effective_from=date(2026, 6, 1),
    )

    assert rows == 1
    sql, params = cursor.executed[0]
    assert "effective_to] IS NULL" in sql
    assert params == (date(2026, 6, 1), "ATVPDKIKX0DER", "SKU-A", date(2026, 6, 1))


def test_db_decimal_quantizes_to_four_places() -> None:
    assert _db_decimal(Decimal("2.1")) == "2.1000"
