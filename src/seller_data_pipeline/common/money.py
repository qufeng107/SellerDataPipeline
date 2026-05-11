from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def to_money(value: int | float | str | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
