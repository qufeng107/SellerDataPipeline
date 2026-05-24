from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

from seller_data_pipeline.services.monthly_financial_close_service import (
    MonthlyFinancialCloseService,
    month_to_date_range,
)


def test_month_to_date_range_handles_month_end() -> None:
    assert month_to_date_range("2026-03") == (date(2026, 3, 1), date(2026, 3, 31))
    assert month_to_date_range("2026-02") == (date(2026, 2, 1), date(2026, 2, 28))


def test_calculate_monthly_financial_close_core_metrics() -> None:
    result = MonthlyFinancialCloseService().calculate_from_rows(
        marketplace_id="ATVPDKIKX0DER",
        profile_id="3917953989967300",
        month="2026-03",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
        settlement_rows=[
            _settlement_row(1, "SKU-1", Decimal("100.00"), "product_sales", "revenue", 2),
            _settlement_row(2, "SKU-1", Decimal("-15.00"), "referral_fee", "amazon_fee", 2),
            _settlement_row(3, "SKU-1", Decimal("-20.00"), "fba_fee", "fba_fee", 2),
            _settlement_row(
                4,
                None,
                Decimal("-10.00"),
                "advertising_fee",
                "advertising_cost",
                None,
            ),
            _settlement_row(5, None, Decimal("5.00"), "reimbursement", "reimbursement", None),
        ],
        sku_cost_rows=[_cost_row("SKU-1", Decimal("20.00"), Decimal("5.00"), date(2026, 1, 1))],
        orders_summary={"order_count": 1, "ordered_units": 2},
        ads_summary={"ads_cost": Decimal("10.00"), "ads_clicks": 9},
        sales_traffic_summary={
            "units_ordered": 2,
            "sessions": 100,
            "ordered_product_sales_amount": Decimal("100.00"),
        },
    )

    assert result.status == "ok"
    assert result.financial_summary.settlement_net_amount == Decimal("60.00")
    assert result.financial_summary.product_sales_amount == Decimal("100.00")
    assert result.financial_summary.product_sales_units == 2
    assert result.financial_summary.internal_cogs == Decimal("50.00")
    assert result.financial_summary.estimated_operating_profit == Decimal("10.00")
    assert result.financial_summary.profit_margin == Decimal("0.1000")
    assert result.sku_profitability[0].unit_standard_cost == Decimal("25.00")
    assert result.sku_profitability[0].estimated_profit_after_cogs == Decimal("15.00")
    assert result.executive_summary()["headline"].startswith("2026-03 estimated operating profit")


def test_missing_sku_cost_marks_needs_review() -> None:
    result = MonthlyFinancialCloseService().calculate_from_rows(
        marketplace_id="ATVPDKIKX0DER",
        profile_id=None,
        month="2026-03",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
        settlement_rows=[
            _settlement_row(
                1,
                "SKU-MISSING",
                Decimal("30.00"),
                "product_sales",
                "revenue",
                1,
            )
        ],
        sku_cost_rows=[],
    )

    assert result.status == "needs_review"
    assert result.financial_summary.internal_cogs == Decimal("0.00")
    assert result.sku_profitability[0].status == "missing_cost"
    assert any(warning.warning_code == "missing_sku_cost" for warning in result.warnings)


def test_missing_ads_api_context_adds_warning_but_keeps_settlement_profit_ok() -> None:
    result = MonthlyFinancialCloseService().calculate_from_rows(
        marketplace_id="ATVPDKIKX0DER",
        profile_id="3917953989967300",
        month="2026-03",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
        settlement_rows=[
            _settlement_row(1, "SKU-1", Decimal("100.00"), "product_sales", "revenue", 1),
            _settlement_row(
                2,
                None,
                Decimal("-10.00"),
                "advertising_fee",
                "advertising_cost",
                None,
            ),
        ],
        sku_cost_rows=[_cost_row("SKU-1", Decimal("20.00"), Decimal("5.00"), date(2026, 1, 1))],
        ads_summary={"ads_cost": Decimal("0.00"), "ads_row_count": 0},
        sales_traffic_summary={"ordered_product_sales_amount": Decimal("100.00")},
    )

    assert result.status == "ok"
    assert result.financial_summary.estimated_operating_profit == Decimal("65.00")
    assert any(warning.warning_code == "ads_api_context_missing" for warning in result.warnings)
    assert "Reconciliation warnings:" in " ".join(result.executive_summary()["key_points"])


def test_monthly_cost_matching_uses_effective_date_per_unit() -> None:
    result = MonthlyFinancialCloseService().calculate_from_rows(
        marketplace_id="ATVPDKIKX0DER",
        profile_id=None,
        month="2026-03",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
        settlement_rows=[
            _settlement_row(
                1,
                "SKU-1",
                Decimal("30.00"),
                "product_sales",
                "revenue",
                1,
                posted_date=date(2026, 3, 1),
                order_item_code="ITEM-1",
            ),
            _settlement_row(
                2,
                "SKU-1",
                Decimal("30.00"),
                "product_sales",
                "revenue",
                1,
                posted_date=date(2026, 3, 20),
                order_item_code="ITEM-2",
            ),
        ],
        sku_cost_rows=[
            _cost_row(
                "SKU-1",
                Decimal("10.00"),
                Decimal("0.00"),
                date(2026, 1, 1),
                date(2026, 3, 10),
            ),
            _cost_row("SKU-1", Decimal("20.00"), Decimal("0.00"), date(2026, 3, 11)),
        ],
    )

    assert result.status == "ok"
    assert result.financial_summary.internal_cogs == Decimal("30.00")
    assert result.sku_profitability[0].unit_standard_cost == Decimal("15.00")
    assert "multiple cost rows matched" in "; ".join(result.sku_profitability[0].notes)


def test_write_report_files_creates_json_and_xlsx(tmp_path: Path) -> None:
    result = MonthlyFinancialCloseService().calculate_from_rows(
        marketplace_id="ATVPDKIKX0DER",
        profile_id="3917953989967300",
        month="2026-03",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
        generated_at_utc=datetime(2026, 4, 1),
        settlement_rows=[
            _settlement_row(1, "SKU-1", Decimal("10.00"), "product_sales", "revenue", 1)
        ],
        sku_cost_rows=[_cost_row("SKU-1", Decimal("2.00"), Decimal("1.00"), date(2026, 1, 1))],
    )

    written = MonthlyFinancialCloseService().write_report_files(result=result, output_root=tmp_path)

    assert set(written.output_files) == {"json", "xlsx"}
    json_path = tmp_path / "ATVPDKIKX0DER/2026-03/monthly_financial_close_2026-03.json"
    xlsx_path = tmp_path / "ATVPDKIKX0DER/2026-03/monthly_financial_close_2026-03.xlsx"
    assert json_path.exists()
    assert xlsx_path.exists()
    workbook = load_workbook(xlsx_path, read_only=True)
    assert workbook.sheetnames == [
        "00_Readme_说明",
        "01_Summary",
        "02_Settlement_Buckets",
        "03_Amount_Categories",
        "04_SKU_Profit",
        "05_Operational_Context",
        "06_Reconciliation_Checks",
        "07_Warnings",
        "08_Raw_Metadata",
    ]


def test_run_uses_repo_and_writes_report(tmp_path: Path) -> None:
    repo = FakeMonthlyRepo()
    result = MonthlyFinancialCloseService(repo=repo).run(
        marketplace_id="ATVPDKIKX0DER",
        profile_id="3917953989967300",
        month="2026-03",
        output_root=tmp_path,
    )

    assert result.status == "ok"
    assert repo.calls == [
        "settlement",
        "costs",
        "orders",
        "ads",
        "sales_traffic",
        "coupon",
        "promotion",
        "reimbursement",
    ]
    assert result.output_files["xlsx"].endswith("monthly_financial_close_2026-03.xlsx")


def _settlement_row(
    row_id: int,
    seller_sku: str | None,
    amount: Decimal,
    amount_category: str,
    profit_bucket: str,
    quantity: int | None,
    *,
    posted_date: date = date(2026, 3, 1),
    order_item_code: str | None = "ITEM-1",
) -> dict[str, object]:
    return {
        "id": row_id,
        "marketplace_id": "ATVPDKIKX0DER",
        "posted_date": posted_date,
        "amount": amount,
        "currency": "USD",
        "settlement_id": "SETTLEMENT-1",
        "transaction_type": "Order",
        "order_id": "ORDER-1",
        "order_item_code": order_item_code if seller_sku else None,
        "seller_sku": seller_sku,
        "quantity_purchased": quantity,
        "amount_category": amount_category,
        "profit_bucket": profit_bucket,
        "is_settlement_summary": False,
    }


def _cost_row(
    sku: str,
    product_cost: Decimal,
    first_mile_cost: Decimal,
    effective_from: date,
    effective_to: date | None = None,
) -> dict[str, object]:
    return {
        "marketplace_id": "ATVPDKIKX0DER",
        "seller_sku": sku,
        "asin": "B000TEST",
        "product_cost": product_cost,
        "first_mile_cost": first_mile_cost,
        "packaging_cost": Decimal("0.00"),
        "other_unit_cost": Decimal("0.00"),
        "currency": "USD",
        "effective_from": effective_from,
        "effective_to": effective_to,
        "remark": "fixture",
    }


class FakeMonthlyRepo:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_settlement_profit_rows(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, object]]:
        self.calls.append("settlement")
        return [_settlement_row(1, "SKU-1", Decimal("20.00"), "product_sales", "revenue", 1)]

    def fetch_sku_cost_rows(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, object]]:
        self.calls.append("costs")
        return [_cost_row("SKU-1", Decimal("5.00"), Decimal("0.00"), date(2026, 1, 1))]

    def fetch_orders_period_summary(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, object]:
        self.calls.append("orders")
        return {"order_count": 1, "ordered_units": 1}

    def fetch_ads_period_summary(
        self,
        *,
        marketplace_id: str,
        profile_id: str | None,
        start_date: date,
        end_date: date,
    ) -> dict[str, object]:
        self.calls.append("ads")
        assert profile_id == "3917953989967300"
        return {"ads_cost": Decimal("0.00")}

    def fetch_sales_traffic_period_summary(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, object]:
        self.calls.append("sales_traffic")
        return {"units_ordered": 1, "ordered_product_sales_amount": Decimal("20.00")}

    def fetch_coupon_period_summary(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, object]:
        self.calls.append("coupon")
        return {"coupon_count": 0}

    def fetch_promotion_period_summary(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, object]:
        self.calls.append("promotion")
        return {"promotion_count": 0}

    def fetch_fba_reimbursement_period_summary(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, object]:
        self.calls.append("reimbursement")
        return {"reimbursement_count": 0}
