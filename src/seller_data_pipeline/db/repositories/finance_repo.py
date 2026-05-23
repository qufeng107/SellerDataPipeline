from __future__ import annotations

from datetime import date
from typing import Any


class FinanceRepo:
    """Read-only repository for first-pass profit preview queries.

    Profit calculation is intentionally read-only in v1. It reads normalized
    ingestion tables and writes preview files outside the database until the
    Settlement-led policy has been manually reconciled across several periods.
    """

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def fetch_settlement_profit_rows(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                WITH normalized AS (
                    SELECT
                        [id],
                        [marketplace_id],
                        [settlement_id],
                        [transaction_type],
                        [order_id],
                        [order_item_code],
                        [seller_sku],
                        [quantity_purchased],
                        [amount_type],
                        [amount_description],
                        [amount],
                        [currency],
                        [amount_category],
                        [profit_bucket],
                        [is_settlement_summary],
                        COALESCE(
                            TRY_CONVERT(date, NULLIF([posted_date_time_raw], ''), 127),
                            TRY_CONVERT(date, NULLIF([posted_date_time_raw], '')),
                            TRY_CONVERT(date, NULLIF([posted_date_raw], ''), 127),
                            TRY_CONVERT(date, NULLIF([posted_date_raw], '')),
                            TRY_CONVERT(date, NULLIF([deposit_date_raw], ''), 127),
                            TRY_CONVERT(date, NULLIF([deposit_date_raw], ''))
                        ) AS [posted_date]
                    FROM dbo.[amazon_settlement_transaction]
                    WHERE [marketplace_id] = ?
                      AND [is_settlement_summary] = 0
                      AND [amount] IS NOT NULL
                )
                SELECT
                    [id],
                    [marketplace_id],
                    [settlement_id],
                    [transaction_type],
                    [order_id],
                    [order_item_code],
                    [seller_sku],
                    [quantity_purchased],
                    [amount_type],
                    [amount_description],
                    [amount],
                    [currency],
                    [amount_category],
                    [profit_bucket],
                    [is_settlement_summary],
                    [posted_date]
                FROM normalized
                WHERE [posted_date] >= ? AND [posted_date] <= ?
                ORDER BY [posted_date], [id];
                """,
                (marketplace_id, start_date, end_date),
            )
            return rows_to_dicts(cursor)
        finally:
            cursor.close()

    def fetch_sku_cost_rows(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    [marketplace_id],
                    [seller_sku],
                    [asin],
                    [product_cost],
                    [first_mile_cost],
                    [packaging_cost],
                    [other_unit_cost],
                    [currency],
                    [effective_from],
                    [effective_to],
                    [remark]
                FROM dbo.[amazon_sku_cost]
                WHERE [marketplace_id] = ?
                  AND [effective_from] <= ?
                  AND ([effective_to] IS NULL OR [effective_to] >= ?)
                ORDER BY [seller_sku], [effective_from] DESC;
                """,
                (marketplace_id, end_date, start_date),
            )
            return rows_to_dicts(cursor)
        finally:
            cursor.close()

    def fetch_orders_period_summary(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                WITH normalized AS (
                    SELECT
                        [amazon_order_id],
                        [quantity],
                        [item_price],
                        [currency],
                        COALESCE(
                            TRY_CONVERT(date, NULLIF([purchase_date_raw], ''), 127),
                            TRY_CONVERT(date, NULLIF([purchase_date_raw], ''))
                        ) AS [purchase_date]
                    FROM dbo.[amazon_order_item]
                    WHERE [marketplace_id] = ?
                )
                SELECT
                    COUNT(DISTINCT [amazon_order_id]) AS [order_count],
                    COUNT_BIG(*) AS [order_item_rows],
                    COALESCE(SUM(COALESCE([quantity], 0)), 0) AS [ordered_units],
                    COALESCE(SUM(COALESCE([item_price], 0)), 0) AS [ordered_item_sales_amount],
                    MIN([currency]) AS [currency]
                FROM normalized
                WHERE [purchase_date] >= ? AND [purchase_date] <= ?;
                """,
                (marketplace_id, start_date, end_date),
            )
            return one_row_to_dict(cursor)
        finally:
            cursor.close()

    def fetch_ads_period_summary(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    COALESCE(SUM(COALESCE([cost], 0)), 0) AS [ads_cost],
                    COALESCE(SUM(COALESCE([sales_7d], 0)), 0) AS [ads_sales_7d],
                    COALESCE(SUM(COALESCE([clicks], 0)), 0) AS [ads_clicks],
                    COALESCE(SUM(COALESCE([impressions], 0)), 0) AS [ads_impressions]
                FROM dbo.[amazon_ads_sp_campaign_daily]
                WHERE [marketplace_id] = ?
                  AND [report_date] >= ?
                  AND [report_date] <= ?;
                """,
                (marketplace_id, start_date, end_date),
            )
            return one_row_to_dict(cursor)
        finally:
            cursor.close()

    def fetch_sales_traffic_period_summary(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    COALESCE(SUM(COALESCE([units_ordered], 0)), 0) AS [units_ordered],
                    COALESCE(SUM(COALESCE([ordered_product_sales_amount], 0)), 0)
                        AS [ordered_product_sales_amount],
                    COALESCE(SUM(COALESCE([sessions], 0)), 0) AS [sessions],
                    COALESCE(SUM(COALESCE([total_order_items], 0)), 0)
                        AS [total_order_items]
                FROM dbo.[amazon_sales_traffic_daily]
                WHERE [marketplace_id] = ?
                  AND [report_date] >= ?
                  AND [report_date] <= ?;
                """,
                (marketplace_id, start_date, end_date),
            )
            return one_row_to_dict(cursor)
        finally:
            cursor.close()


def rows_to_dicts(cursor: Any) -> list[dict[str, Any]]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def one_row_to_dict(cursor: Any) -> dict[str, Any]:
    columns = [column[0] for column in cursor.description]
    row = cursor.fetchone()
    if row is None:
        return {}
    return dict(zip(columns, row, strict=True))


__all__ = ["FinanceRepo", "one_row_to_dict", "rows_to_dicts"]
