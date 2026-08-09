from __future__ import annotations


def settlement_date_sql(*columns: str) -> str:
    """Build an unambiguous SQL Server date expression for Settlement raw dates.

    Amazon Settlement V2 has been observed with both ISO dates (YYYY-MM-DD) and
    dot-separated European-style dates (DD.MM.YYYY). SQL Server's session-dependent
    implicit conversion can misread values such as 07.03.2026 as July 3 instead of
    7 March. This helper deliberately uses explicit styles only and never falls back
    to an unstyled TRY_CONVERT.
    """

    if not columns:
        raise ValueError("At least one Settlement raw-date column is required")

    attempts: list[str] = []
    for column in columns:
        value = f"NULLIF(LTRIM(RTRIM({column})), '')"
        prefix = f"LEFT({value}, 10)"
        attempts.extend(
            (
                # ISO calendar date: YYYY-MM-DD, including timestamps whose first
                # ten characters use the same form.
                f"TRY_CONVERT(date, {prefix}, 23)",
                # Amazon-generated Settlement reports can use DD.MM.YYYY.
                f"TRY_CONVERT(date, {prefix}, 104)",
                # Compact ISO calendar date, kept for defensive compatibility.
                f"TRY_CONVERT(date, {value}, 112)",
            )
        )
    return "COALESCE(\n                            " + ",\n                            ".join(attempts) + "\n                        )"


__all__ = ["settlement_date_sql"]
