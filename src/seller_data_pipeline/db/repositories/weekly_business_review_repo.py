from __future__ import annotations

from datetime import date
from typing import Any

from seller_data_pipeline.db.repositories.finance_repo import rows_to_dicts
from seller_data_pipeline.db.settlement_sql import settlement_date_sql
from seller_data_pipeline.integrations.amazon.marketplaces import expected_marketplace_currency


class WeeklyBusinessReviewRepo:
    """Read-only repository for Weekly Business Review v1.

    WBR v1 remains a file-output report. This repository only reads normalized
    tables and intentionally never writes report result rows or migrations.
    """

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def fetch_sales_traffic_daily_rows(
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
                    [report_date],
                    [ordered_product_sales_amount],
                    [ordered_product_sales_currency],
                    [units_ordered],
                    [total_order_items],
                    [sessions],
                    [page_views],
                    [units_refunded],
                    [refund_rate]
                FROM dbo.[amazon_sales_traffic_daily]
                WHERE [marketplace_id] = ?
                  AND [report_date] >= ?
                  AND [report_date] <= ?
                ORDER BY [report_date];
                """,
                (marketplace_id, start_date, end_date),
            )
            return rows_to_dicts(cursor)
        finally:
            cursor.close()

    def fetch_order_item_rows(
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
                        [amazon_order_id],
                        [purchase_date_raw],
                        COALESCE(
                            TRY_CONVERT(date, NULLIF([purchase_date_raw], ''), 127),
                            TRY_CONVERT(date, NULLIF([purchase_date_raw], ''))
                        ) AS [purchase_date],
                        [order_status],
                        [item_status],
                        [product_name],
                        [seller_sku],
                        [asin],
                        [quantity],
                        [currency],
                        [item_price],
                        [shipping_price],
                        [item_promotion_discount],
                        [ship_promotion_discount]
                    FROM dbo.[amazon_order_item]
                    WHERE [marketplace_id] = ?
                )
                SELECT
                    [amazon_order_id],
                    [purchase_date_raw],
                    [purchase_date],
                    [order_status],
                    [item_status],
                    [product_name],
                    [seller_sku],
                    [asin],
                    [quantity],
                    [currency],
                    [item_price],
                    [shipping_price],
                    [item_promotion_discount],
                    [ship_promotion_discount]
                FROM normalized
                WHERE [purchase_date] >= ?
                  AND [purchase_date] <= ?
                  AND ([order_status] IS NULL OR [order_status] NOT IN ('Cancelled', 'Canceled'))
                  AND ([item_status] IS NULL OR [item_status] NOT IN ('Cancelled', 'Canceled'))
                ORDER BY [purchase_date], [amazon_order_id], [seller_sku];
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

    def fetch_ads_campaign_daily_rows(
        self,
        *,
        marketplace_id: str,
        profile_id: str | None,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
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
                    [profile_id],
                    [marketplace_id],
                    [report_date],
                    [campaign_id],
                    [campaign_name],
                    [campaign_status],
                    [impressions],
                    [clicks],
                    [cost],
                    [sales_7d],
                    [purchases_7d],
                    [units_sold_clicks_7d]
                FROM dbo.[amazon_ads_sp_campaign_daily]
                WHERE [marketplace_id] = ?
                  {where_profile}
                  AND [report_date] >= ?
                  AND [report_date] <= ?
                ORDER BY [report_date], [campaign_name], [campaign_id];
                """,
                params,
            )
            return rows_to_dicts(cursor)
        finally:
            cursor.close()

    def fetch_ads_advertised_product_daily_rows(
        self,
        *,
        marketplace_id: str,
        profile_id: str | None,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
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
                    [profile_id],
                    [marketplace_id],
                    [report_date],
                    [campaign_id],
                    [campaign_name],
                    [ad_group_id],
                    [ad_group_name],
                    [advertised_asin],
                    [advertised_sku],
                    [impressions],
                    [clicks],
                    [cost],
                    [sales_7d],
                    [purchases_7d],
                    [units_sold_clicks_7d]
                FROM dbo.[amazon_ads_sp_advertised_product_daily]
                WHERE [marketplace_id] = ?
                  {where_profile}
                  AND [report_date] >= ?
                  AND [report_date] <= ?
                ORDER BY [report_date], [advertised_sku], [campaign_name];
                """,
                params,
            )
            return rows_to_dicts(cursor)
        finally:
            cursor.close()

    def fetch_latest_inventory_rows(
        self,
        *,
        marketplace_id: str,
        as_of_date: date,
    ) -> list[dict[str, Any]]:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                WITH latest AS (
                    SELECT MAX([snapshot_date]) AS [snapshot_date]
                    FROM dbo.[amazon_inventory_daily]
                    WHERE [marketplace_id] = ?
                      AND [snapshot_date] <= ?
                )
                SELECT
                    inv.[snapshot_date],
                    inv.[seller_sku],
                    inv.[fnsku],
                    inv.[asin],
                    inv.[product_name],
                    inv.[afn_fulfillable_quantity],
                    inv.[afn_reserved_quantity],
                    inv.[afn_unsellable_quantity],
                    inv.[afn_total_quantity],
                    inv.[afn_warehouse_quantity],
                    inv.[currency]
                FROM dbo.[amazon_inventory_daily] AS inv
                INNER JOIN latest
                    ON inv.[snapshot_date] = latest.[snapshot_date]
                WHERE inv.[marketplace_id] = ?
                ORDER BY inv.[seller_sku];
                """,
                (marketplace_id, as_of_date, marketplace_id),
            )
            return rows_to_dicts(cursor)
        finally:
            cursor.close()

    def fetch_latest_listing_rows(
        self,
        *,
        marketplace_id: str,
        as_of_date: date,
    ) -> list[dict[str, Any]]:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                WITH latest AS (
                    SELECT MAX([snapshot_date]) AS [snapshot_date]
                    FROM dbo.[amazon_listing_snapshot]
                    WHERE [marketplace_id] = ?
                      AND [snapshot_date] <= ?
                )
                SELECT
                    lst.[snapshot_date],
                    lst.[seller_sku],
                    lst.[asin],
                    lst.[item_name],
                    lst.[price],
                    lst.[currency],
                    lst.[status],
                    lst.[fulfillment_channel]
                FROM dbo.[amazon_listing_snapshot] AS lst
                INNER JOIN latest
                    ON lst.[snapshot_date] = latest.[snapshot_date]
                WHERE lst.[marketplace_id] = ?
                ORDER BY lst.[seller_sku];
                """,
                (marketplace_id, as_of_date, marketplace_id),
            )
            return rows_to_dicts(cursor)
        finally:
            cursor.close()

    def fetch_settlement_preview_rows(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        cursor = self.connection.cursor()
        try:
            posted_date_expression = settlement_date_sql(
                "[posted_date_time_raw]",
                "[posted_date_raw]",
                "[deposit_date_raw]",
            )
            expected_currency = expected_marketplace_currency(marketplace_id)
            currency_filter = ""
            params: tuple[Any, ...]
            if expected_currency:
                currency_filter = " AND UPPER(NULLIF([currency], '')) = ?"
                params = (marketplace_id, expected_currency, start_date, end_date)
            else:
                params = (marketplace_id, start_date, end_date)
            cursor.execute(
                f"""
                WITH normalized AS (
                    SELECT
                        [id],
                        [transaction_type],
                        [seller_sku],
                        [amount],
                        [currency],
                        [amount_category],
                        [profit_bucket],
                        {posted_date_expression} AS [posted_date]
                    FROM dbo.[amazon_settlement_transaction]
                    WHERE [marketplace_id] = ?
                      AND [is_settlement_summary] = 0
                      AND [amount] IS NOT NULL
                      {currency_filter}
                )
                SELECT
                    [id],
                    [transaction_type],
                    [seller_sku],
                    [amount],
                    [currency],
                    [amount_category],
                    [profit_bucket],
                    [posted_date]
                FROM normalized
                WHERE [posted_date] >= ? AND [posted_date] <= ?
                ORDER BY [posted_date], [id];
                """,
                params,
            )
            return rows_to_dicts(cursor)
        finally:
            cursor.close()


__all__ = ["WeeklyBusinessReviewRepo"]
