from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ProfitInput:
    sales_amount: Decimal
    amazon_fees: Decimal = Decimal("0")
    fba_fees: Decimal = Decimal("0")
    refund_amount: Decimal = Decimal("0")
    ad_spend: Decimal = Decimal("0")
    promotion_cost: Decimal = Decimal("0")
    product_cost: Decimal = Decimal("0")
    first_mile_cost: Decimal = Decimal("0")
    other_cost: Decimal = Decimal("0")


class CalculateProfitService:
    def estimate_profit(self, data: ProfitInput) -> Decimal:
        return (
            data.sales_amount
            - data.amazon_fees
            - data.fba_fees
            - data.refund_amount
            - data.ad_spend
            - data.promotion_cost
            - data.product_cost
            - data.first_mile_cost
            - data.other_cost
        )
