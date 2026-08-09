from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal

from seller_data_pipeline.ingestion import settlement_marketplace_integrity_repair as module
from seller_data_pipeline.ingestion.settlement_marketplace_integrity_repair import (
    SettlementMarketplaceIntegrityRepairService,
    build_marketplace_integrity_plans,
)


def _row(
    row_id: int,
    report_id: str,
    currency: str | None,
    *,
    amount: str = "1.00",
) -> dict[str, object]:
    return {
        "id": row_id,
        "marketplace_id": "ATVPDKIKX0DER",
        "source_report_id": report_id,
        "currency": currency,
        "marketplace_name": None,
        "source_raw_file_path": f"{report_id}.txt",
        "amount": Decimal(amount),
    }


def test_build_marketplace_integrity_plans_marks_whole_foreign_currency_report_repairable() -> None:
    plans = build_marketplace_integrity_plans(
        rows=[
            _row(1, "cad-report", "CAD", amount="-19.37"),
            _row(2, "cad-report", "CAD", amount="0"),
            _row(3, "usd-report", "USD", amount="10"),
        ],
        expected_currency="USD",
    )

    assert len(plans) == 1
    plan = plans[0]
    assert plan.source_report_id == "cad-report"
    assert plan.status == "repairable"
    assert plan.observed_currencies == ("CAD",)
    assert plan.row_ids == (1, 2)
    assert plan.amount_total == Decimal("-19.37")


def test_build_marketplace_integrity_plans_blocks_mixed_currency_report() -> None:
    plans = build_marketplace_integrity_plans(
        rows=[_row(1, "mixed", "USD"), _row(2, "mixed", "CAD")],
        expected_currency="USD",
    )

    assert len(plans) == 1
    assert plans[0].status == "conflict"
    assert plans[0].requires_review is True


class FakeConnection:
    pass


class FakeRepo:
    def __init__(self) -> None:
        self.rows = [_row(1, "cad-report", "CAD", amount="-19.37")]
        self.deleted: list[int] = []
        self.commit_count = 0
        self.rollback_count = 0

    def fetch_marketplace_integrity_rows(self, *, marketplace_id: str):
        assert marketplace_id == "ATVPDKIKX0DER"
        return list(self.rows)

    def delete_transaction_rows_by_ids(self, row_ids):  # noqa: ANN001
        self.deleted.extend(row_ids)
        return len(row_ids)

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1


@contextmanager
def _fake_connection(*, autocommit=False):  # noqa: ANN001
    assert autocommit is False
    yield FakeConnection()


def test_marketplace_integrity_service_executes_repairable_foreign_currency_report(monkeypatch) -> None:
    repo = FakeRepo()
    monkeypatch.setattr(module, "get_connection", _fake_connection)
    monkeypatch.setattr(module, "SettlementRepo", lambda conn: repo)

    result = SettlementMarketplaceIntegrityRepairService().run(
        marketplace_id="ATVPDKIKX0DER",
        execute=True,
    )

    assert result.status == "success"
    assert result.rows_deleted == 1
    assert repo.deleted == [1]
    assert repo.commit_count == 1
    assert repo.rollback_count == 0
