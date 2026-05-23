from __future__ import annotations

from typing import Any

from seller_data_pipeline.db.repositories.report_email_recipient_repo import (
    ReportEmailRecipientRepo,
)


def test_fetch_enabled_recipients_orders_by_specificity() -> None:
    connection = _FakeConnection(
        rows=[
            {
                "report_type": "weekly_ads_optimization",
                "audience": "ads_operator",
                "recipient_type": "to",
                "email": "feng@cuidena.cn",
                "display_name": "Feng",
                "sort_order": 10,
                "specificity_rank": 1,
            },
            {
                "report_type": "*",
                "audience": "*",
                "recipient_type": "cc",
                "email": "qian@cuidena.cn",
                "display_name": "Qian",
                "sort_order": 30,
                "specificity_rank": 4,
            },
        ]
    )

    rows = ReportEmailRecipientRepo(connection).fetch_enabled_recipients(
        report_type="weekly_ads_optimization",
        audience="ads_operator",
    )

    assert len(rows) == 2
    assert rows[0].email == "feng@cuidena.cn"
    assert rows[0].specificity_rank == 1
    assert rows[1].recipient_type == "cc"
    assert connection.cursor_obj.closed is True
    assert connection.cursor_obj.params == (
        "weekly_ads_optimization",
        "ads_operator",
        "weekly_ads_optimization",
        "ads_operator",
        "weekly_ads_optimization",
        "ads_operator",
    )


class _FakeConnection:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.cursor_obj = _FakeCursor(rows)

    def cursor(self) -> _FakeCursor:
        return self.cursor_obj


class _FakeCursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.description = [(name,) for name in rows[0]] if rows else []
        self._rows = [tuple(row.values()) for row in rows]
        self.params: tuple[Any, ...] | None = None
        self.closed = False

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self.sql = sql
        self.params = params

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows

    def close(self) -> None:
        self.closed = True
