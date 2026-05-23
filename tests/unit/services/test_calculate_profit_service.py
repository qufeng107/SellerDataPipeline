from __future__ import annotations

from datetime import date
from decimal import Decimal

from seller_data_pipeline.services.calculate_profit_service import (
    CalculateProfitService,
    ProfitInput,
)


def test_estimate_profit() -> None:
    data = ProfitInput(
        sales_amount=Decimal("100.00"),
        amazon_fees=Decimal("15.00"),
        fba_fees=Decimal("20.00"),
        refund_amount=Decimal("0.00"),
        ad_spend=Decimal("10.00"),
        promotion_cost=Decimal("5.00"),
        product_cost=Decimal("25.00"),
        first_mile_cost=Decimal("8.00"),
        other_cost=Decimal("2.00"),
    )
    assert CalculateProfitService().estimate_profit(data) == Decimal("15.00")


def test_calculate_from_rows_uses_settlement_net_and_sku_costs() -> None:
    result = CalculateProfitService().calculate_from_rows(
        marketplace_id="ATVPDKIKX0DER",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 7),
        settlement_rows=[
            _settlement_row(
                row_id=1,
                seller_sku="SKU-1",
                amount=Decimal("40.00"),
                amount_category="product_sales",
                profit_bucket="revenue",
                quantity=2,
            ),
            _settlement_row(
                row_id=2,
                seller_sku="SKU-1",
                amount=Decimal("-6.00"),
                amount_category="referral_fee",
                profit_bucket="amazon_fee",
                quantity=2,
            ),
            _settlement_row(
                row_id=3,
                seller_sku="SKU-1",
                amount=Decimal("-8.00"),
                amount_category="fba_fulfillment_fee",
                profit_bucket="fba_fee",
                quantity=2,
            ),
            _settlement_row(
                row_id=4,
                seller_sku=None,
                amount=Decimal("-3.00"),
                amount_category="advertising_fee",
                profit_bucket="advertising_cost",
                quantity=None,
            ),
        ],
        sku_cost_rows=[
            {
                "marketplace_id": "ATVPDKIKX0DER",
                "seller_sku": "SKU-1",
                "asin": "B000TEST",
                "product_cost": Decimal("5.00"),
                "first_mile_cost": Decimal("1.00"),
                "packaging_cost": Decimal("0.50"),
                "other_unit_cost": Decimal("0.25"),
                "currency": "USD",
                "effective_from": date(2026, 1, 1),
                "effective_to": None,
                "remark": "fixture",
            }
        ],
        orders_summary={"order_count": 1, "ordered_units": 2},
        ads_summary={"ads_cost": Decimal("3.00"), "ads_clicks": 7},
        sales_traffic_summary={"units_ordered": 2, "sessions": 100},
    )

    assert result.status == "ok"
    assert result.settlement_net_amount == Decimal("23.00")
    assert result.product_sales_units == 2
    assert result.product_sales_amount == Decimal("40.00")
    assert result.internal_cogs == Decimal("13.50")
    assert result.estimated_operating_profit == Decimal("9.50")
    assert result.bucket_totals["amazon_fee"] == Decimal("-6.00")
    assert result.operational_summary.order_count == 1
    assert result.operational_summary.ads_clicks == 7
    assert len(result.sku_rows) == 1
    assert result.sku_rows[0].unit_standard_cost == Decimal("6.75")


def test_calculate_from_rows_flags_missing_cost_and_does_not_publish_ok() -> None:
    result = CalculateProfitService().calculate_from_rows(
        marketplace_id="ATVPDKIKX0DER",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 7),
        settlement_rows=[
            _settlement_row(
                row_id=1,
                seller_sku="SKU-MISSING",
                amount=Decimal("20.00"),
                amount_category="product_sales",
                profit_bucket="revenue",
                quantity=1,
            )
        ],
        sku_cost_rows=[],
    )

    assert result.status == "needs_review"
    assert result.missing_cost_skus == ("SKU-MISSING",)
    assert result.internal_cogs == Decimal("0.00")
    assert any("Missing amazon_sku_cost" in warning for warning in result.warnings)


def test_write_preview_files_creates_json_markdown_and_sku_csv(tmp_path) -> None:
    result = CalculateProfitService().calculate_from_rows(
        marketplace_id="ATVPDKIKX0DER",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 1),
        settlement_rows=[
            _settlement_row(
                row_id=1,
                seller_sku="SKU-1",
                amount=Decimal("10.00"),
                amount_category="product_sales",
                profit_bucket="revenue",
                quantity=1,
            )
        ],
        sku_cost_rows=[
            {
                "marketplace_id": "ATVPDKIKX0DER",
                "seller_sku": "SKU-1",
                "asin": "B000TEST",
                "product_cost": Decimal("2.00"),
                "first_mile_cost": Decimal("1.00"),
                "packaging_cost": Decimal("0.50"),
                "other_unit_cost": Decimal("0.00"),
                "currency": "USD",
                "effective_from": date(2026, 1, 1),
            }
        ],
    )

    written = CalculateProfitService().write_preview_files(result=result, output_root=tmp_path)

    assert set(written.output_files) == {"json", "markdown", "sku_csv"}
    for path in written.output_files.values():
        assert (tmp_path / path.replace(str(tmp_path) + "/", "")).exists()
    markdown = (tmp_path / "ATVPDKIKX0DER/2026-05-01_2026-05-01/profit_preview.md").read_text(
        encoding="utf-8"
    )
    assert "Settlement-led" in markdown
    assert "SKU-1" in markdown


def test_run_uses_repo_and_writes_preview(tmp_path) -> None:
    repo = FakeProfitRepo()
    result = CalculateProfitService(repo=repo).run(
        marketplace_id="ATVPDKIKX0DER",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 1),
        output_root=tmp_path,
    )

    assert result.status == "ok"
    assert repo.calls == [
        "settlement",
        "costs",
        "orders",
        "ads",
        "sales_traffic",
    ]
    assert result.output_files["json"].endswith("profit_preview.json")


def _settlement_row(
    *,
    row_id: int,
    seller_sku: str | None,
    amount: Decimal,
    amount_category: str,
    profit_bucket: str,
    quantity: int | None,
) -> dict[str, object]:
    return {
        "id": row_id,
        "marketplace_id": "ATVPDKIKX0DER",
        "posted_date": date(2026, 5, 1),
        "amount": amount,
        "currency": "USD",
        "settlement_id": "SETTLEMENT-1",
        "transaction_type": "Order",
        "order_id": "ORDER-1",
        "order_item_code": "ITEM-1" if seller_sku else None,
        "seller_sku": seller_sku,
        "quantity_purchased": quantity,
        "amount_category": amount_category,
        "profit_bucket": profit_bucket,
        "is_settlement_summary": False,
    }


class FakeProfitRepo:
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
        return [
            _settlement_row(
                row_id=1,
                seller_sku="SKU-1",
                amount=Decimal("10.00"),
                amount_category="product_sales",
                profit_bucket="revenue",
                quantity=1,
            )
        ]

    def fetch_sku_cost_rows(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, object]]:
        self.calls.append("costs")
        return [
            {
                "marketplace_id": marketplace_id,
                "seller_sku": "SKU-1",
                "asin": "B000TEST",
                "product_cost": Decimal("2.00"),
                "first_mile_cost": Decimal("1.00"),
                "packaging_cost": Decimal("0.50"),
                "other_unit_cost": Decimal("0.00"),
                "currency": "USD",
                "effective_from": start_date,
            }
        ]

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
        start_date: date,
        end_date: date,
    ) -> dict[str, object]:
        self.calls.append("ads")
        return {"ads_cost": Decimal("0.00")}

    def fetch_sales_traffic_period_summary(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, object]:
        self.calls.append("sales_traffic")
        return {"units_ordered": 1}
