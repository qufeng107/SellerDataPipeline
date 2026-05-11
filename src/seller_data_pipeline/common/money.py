from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def to_money(value: int | float | str | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
