from __future__ import annotations

from datetime import date
from typing import Any

from seller_data_pipeline.db.repositories.finance_repo import one_row_to_dict, rows_to_dicts


class MonthlyFinancialCloseRepo:
    """Read-only repository for Monthly Financial Close Report v1.

    The report remains file-output only in v1. This repository intentionally performs
    read-only queries against normalized tables and never writes report result rows.
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
                        [source_report_id],
                        [source_raw_file_path],
                        [source_run_id],
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
                    [source_report_id],
                    [source_raw_file_path],
                    [source_run_id],
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
                        [item_promotion_discount],
                        [ship_promotion_discount],
                        [currency],
                        [order_status],
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
                    COALESCE(SUM(COALESCE([item_price], 0)), 0)
                        AS [ordered_item_sales_amount],
                    COALESCE(SUM(COALESCE([item_promotion_discount], 0)), 0)
                        AS [item_promotion_discount_amount],
                    COALESCE(SUM(COALESCE([ship_promotion_discount], 0)), 0)
                        AS [ship_promotion_discount_amount],
                    COALESCE(SUM(
                        CASE
                            WHEN [order_status] IS NULL THEN 0
                            WHEN [order_status] IN ('Cancelled', 'Canceled') THEN 1
                            ELSE 0
                        END
                    ), 0) AS [order_exception_count],
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
        profile_id: str | None,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        cursor = self.connection.cursor()
        try:
            where_profile = ""
            params: tuple[Any, ...]
            if profile_id:
                where_profile = " AND [profile_id] = ?"
                params = (marketplace_id, profile_id, start_date, end_date)
            else:
                params = (marketplace_id, start_date, end_date)
            cursor.execute(
                f"""
                SELECT
                    COALESCE(SUM(COALESCE([cost], 0)), 0) AS [ads_cost],
                    COALESCE(SUM(COALESCE([sales_7d], 0)), 0) AS [ads_sales_7d],
                    COALESCE(SUM(COALESCE([clicks], 0)), 0) AS [ads_clicks],
                    COALESCE(SUM(COALESCE([impressions], 0)), 0) AS [ads_impressions],
                    COALESCE(SUM(COALESCE([purchases_7d], 0)), 0) AS [ads_purchases_7d],
                    COUNT_BIG(*) AS [ads_row_count]
                FROM dbo.[amazon_ads_sp_campaign_daily]
                WHERE [marketplace_id] = ?
                  {where_profile}
                  AND [report_date] >= ?
                  AND [report_date] <= ?;
                """,
                params,
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
                    MIN([ordered_product_sales_currency]) AS [ordered_product_sales_currency],
                    COALESCE(SUM(COALESCE([sessions], 0)), 0) AS [sessions],
                    COALESCE(SUM(COALESCE([page_views], 0)), 0) AS [page_views],
                    COALESCE(SUM(COALESCE([total_order_items], 0)), 0)
                        AS [total_order_items],
                    COALESCE(SUM(COALESCE([units_refunded], 0)), 0) AS [units_refunded],
                    COUNT_BIG(*) AS [sales_traffic_row_count]
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

    def fetch_coupon_period_summary(
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
                        [coupon_id],
                        [clips],
                        [redemptions],
                        [total_discount],
                        [budget_spent],
                        [sales],
                        [currency_code],
                        COALESCE(
                            TRY_CONVERT(date, NULLIF([start_date_time_raw], ''), 127),
                            TRY_CONVERT(date, NULLIF([start_date_time_raw], ''))
                        ) AS [start_date],
                        COALESCE(
                            TRY_CONVERT(date, NULLIF([end_date_time_raw], ''), 127),
                            TRY_CONVERT(date, NULLIF([end_date_time_raw], ''))
                        ) AS [end_date]
                    FROM dbo.[amazon_coupon_performance]
                    WHERE [marketplace_id] = ?
                )
                SELECT
                    COUNT(DISTINCT [coupon_id]) AS [coupon_count],
                    COALESCE(SUM(COALESCE([clips], 0)), 0) AS [coupon_clips],
                    COALESCE(SUM(COALESCE([redemptions], 0)), 0)
                        AS [coupon_redemptions],
                    COALESCE(SUM(COALESCE([total_discount], 0)), 0)
                        AS [coupon_total_discount],
                    COALESCE(SUM(COALESCE([budget_spent], 0)), 0)
                        AS [coupon_budget_spent],
                    COALESCE(SUM(COALESCE([sales], 0)), 0) AS [coupon_sales],
                    MIN([currency_code]) AS [coupon_currency]
                FROM normalized
                WHERE ([start_date] IS NULL OR [start_date] <= ?)
                  AND ([end_date] IS NULL OR [end_date] >= ?);
                """,
                (marketplace_id, end_date, start_date),
            )
            return one_row_to_dict(cursor)
        finally:
            cursor.close()

    def fetch_promotion_period_summary(
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
                        [promotion_id],
                        [glance_views],
                        [units_sold],
                        [revenue],
                        [revenue_currency_code],
                        COALESCE(
                            TRY_CONVERT(date, NULLIF([start_date_time_raw], ''), 127),
                            TRY_CONVERT(date, NULLIF([start_date_time_raw], ''))
                        ) AS [start_date],
                        COALESCE(
                            TRY_CONVERT(date, NULLIF([end_date_time_raw], ''), 127),
                            TRY_CONVERT(date, NULLIF([end_date_time_raw], ''))
                        ) AS [end_date]
                    FROM dbo.[amazon_promotion_performance]
                    WHERE [marketplace_id] = ?
                )
                SELECT
                    COUNT(DISTINCT [promotion_id]) AS [promotion_count],
                    COALESCE(SUM(COALESCE([glance_views], 0)), 0)
                        AS [promotion_glance_views],
                    COALESCE(SUM(COALESCE([units_sold], 0)), 0)
                        AS [promotion_units_sold],
                    COALESCE(SUM(COALESCE([revenue], 0)), 0) AS [promotion_revenue],
                    MIN([revenue_currency_code]) AS [promotion_currency]
                FROM normalized
                WHERE ([start_date] IS NULL OR [start_date] <= ?)
                  AND ([end_date] IS NULL OR [end_date] >= ?);
                """,
                (marketplace_id, end_date, start_date),
            )
            return one_row_to_dict(cursor)
        finally:
            cursor.close()

    def fetch_fba_reimbursement_period_summary(
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
                        [reimbursement_id],
                        [reason],
                        [amount_total],
                        [quantity_reimbursed_total],
                        [currency],
                        COALESCE(
                            TRY_CONVERT(date, NULLIF([approval_date_raw], ''), 127),
                            TRY_CONVERT(date, NULLIF([approval_date_raw], ''))
                        ) AS [approval_date]
                    FROM dbo.[amazon_fba_reimbursement]
                    WHERE [marketplace_id] = ?
                )
                SELECT
                    COUNT(DISTINCT [reimbursement_id]) AS [reimbursement_count],
                    COALESCE(SUM(COALESCE([amount_total], 0)), 0)
                        AS [reimbursement_report_amount],
                    COALESCE(SUM(COALESCE([quantity_reimbursed_total], 0)), 0)
                        AS [reimbursement_quantity],
                    COUNT(DISTINCT [reason]) AS [reimbursement_reason_count],
                    MIN([currency]) AS [reimbursement_currency]
                FROM normalized
                WHERE [approval_date] >= ? AND [approval_date] <= ?;
                """,
                (marketplace_id, start_date, end_date),
            )
            return one_row_to_dict(cursor)
        finally:
            cursor.close()


__all__ = ["MonthlyFinancialCloseRepo"]
