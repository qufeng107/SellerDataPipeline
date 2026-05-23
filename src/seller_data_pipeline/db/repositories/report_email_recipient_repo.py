from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from seller_data_pipeline.db.repositories.finance_repo import rows_to_dicts


@dataclass(frozen=True)
class ReportEmailRecipientRecord:
    """Enabled recipient row for report email routing."""

    report_type: str
    audience: str
    recipient_type: str
    email: str
    display_name: str | None
    sort_order: int
    specificity_rank: int


class ReportEmailRecipientRepo:
    """Read-only repository for report email recipient routing."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def fetch_enabled_recipients(
        self,
        *,
        report_type: str,
        audience: str,
    ) -> list[ReportEmailRecipientRecord]:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    [report_type],
                    [audience],
                    [recipient_type],
                    [email],
                    [display_name],
                    [sort_order],
                    CASE
                        WHEN [report_type] = ? AND [audience] = ? THEN 1
                        WHEN [report_type] = ? AND [audience] = '*' THEN 2
                        WHEN [report_type] = '*' AND [audience] = ? THEN 3
                        ELSE 4
                    END AS [specificity_rank]
                FROM dbo.[report_email_recipient_config]
                WHERE [enabled] = 1
                  AND [report_type] IN (?, '*')
                  AND [audience] IN (?, '*')
                ORDER BY
                    [specificity_rank],
                    CASE [recipient_type]
                        WHEN 'to' THEN 1
                        WHEN 'cc' THEN 2
                        WHEN 'bcc' THEN 3
                        ELSE 9
                    END,
                    [sort_order],
                    [email];
                """,
                (
                    report_type,
                    audience,
                    report_type,
                    audience,
                    report_type,
                    audience,
                ),
            )
            return [_record_from_row(row) for row in rows_to_dicts(cursor)]
        finally:
            cursor.close()


def _record_from_row(row: dict[str, Any]) -> ReportEmailRecipientRecord:
    return ReportEmailRecipientRecord(
        report_type=str(row.get("report_type") or ""),
        audience=str(row.get("audience") or ""),
        recipient_type=str(row.get("recipient_type") or ""),
        email=str(row.get("email") or ""),
        display_name=str(row["display_name"]) if row.get("display_name") is not None else None,
        sort_order=int(row.get("sort_order") or 0),
        specificity_rank=int(row.get("specificity_rank") or 99),
    )
