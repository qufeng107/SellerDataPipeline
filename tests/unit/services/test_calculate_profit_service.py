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
