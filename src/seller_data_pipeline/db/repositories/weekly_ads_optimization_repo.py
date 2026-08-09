from __future__ import annotations

from datetime import date
from typing import Any

from seller_data_pipeline.db.repositories.finance_repo import one_row_to_dict, rows_to_dicts
from seller_data_pipeline.db.settlement_sql import settlement_date_sql
from seller_data_pipeline.integrations.amazon.marketplaces import expected_marketplace_currency


class WeeklyAdsOptimizationRepo:
    """Read-only repository for Weekly Ads Optimization Report v1.

    WAOR v1 is a file-output report. This repository only reads normalized
    Ads/Sales/Cost/Settlement tables and intentionally never writes report results.
    """

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def fetch_campaign_daily_rows(
        self,
        *,
        marketplace_id: str,
        profile_id: str | None,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        return self._fetch_ads_rows(
            table_name="amazon_ads_sp_campaign_daily",
            columns=(
                "[profile_id]",
                "[marketplace_id]",
                "[report_date]",
                "[campaign_id]",
                "[campaign_name]",
                "[campaign_status]",
                "[impressions]",
                "[clicks]",
                "[cost]",
                "[sales_7d]",
                "[purchases_7d]",
                "[units_sold_clicks_7d]",
            ),
            marketplace_id=marketplace_id,
            profile_id=profile_id,
            start_date=start_date,
            end_date=end_date,
            order_by="[report_date], [campaign_name], [campaign_id]",
        )

    def fetch_targeting_daily_rows(
        self,
        *,
        marketplace_id: str,
        profile_id: str | None,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        return self._fetch_ads_rows(
            table_name="amazon_ads_sp_targeting_daily",
            columns=(
                "[profile_id]",
                "[marketplace_id]",
                "[report_date]",
                "[campaign_id]",
                "[campaign_name]",
                "[ad_group_id]",
                "[ad_group_name]",
                "[keyword_id]",
                "[keyword]",
                "[match_type]",
                "[targeting]",
                "[impressions]",
                "[clicks]",
                "[cost]",
                "[sales_7d]",
                "[purchases_7d]",
                "[units_sold_clicks_7d]",
            ),
            marketplace_id=marketplace_id,
            profile_id=profile_id,
            start_date=start_date,
            end_date=end_date,
            order_by="[report_date], [campaign_name], [ad_group_name], [keyword_id]",
        )

    def fetch_search_term_daily_rows(
        self,
        *,
        marketplace_id: str,
        profile_id: str | None,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        return self._fetch_ads_rows(
            table_name="amazon_ads_sp_search_term_daily",
            columns=(
                "[profile_id]",
                "[marketplace_id]",
                "[report_date]",
                "[campaign_id]",
                "[campaign_name]",
                "[ad_group_id]",
                "[ad_group_name]",
                "[keyword_id]",
                "[keyword]",
                "[match_type]",
                "[targeting]",
                "[search_term]",
                "[impressions]",
                "[clicks]",
                "[cost]",
                "[sales_7d]",
                "[purchases_7d]",
                "[units_sold_clicks_7d]",
            ),
            marketplace_id=marketplace_id,
            profile_id=profile_id,
            start_date=start_date,
            end_date=end_date,
            order_by="[report_date], [campaign_name], [ad_group_name], [search_term]",
        )

    def fetch_advertised_product_daily_rows(
        self,
        *,
        marketplace_id: str,
        profile_id: str | None,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        return self._fetch_ads_rows(
            table_name="amazon_ads_sp_advertised_product_daily",
            columns=(
                "[profile_id]",
                "[marketplace_id]",
                "[report_date]",
                "[campaign_id]",
                "[campaign_name]",
                "[ad_group_id]",
                "[ad_group_name]",
                "[advertised_asin]",
                "[advertised_sku]",
                "[impressions]",
                "[clicks]",
                "[cost]",
                "[sales_7d]",
                "[purchases_7d]",
                "[units_sold_clicks_7d]",
            ),
            marketplace_id=marketplace_id,
            profile_id=profile_id,
            start_date=start_date,
            end_date=end_date,
            order_by="[report_date], [advertised_sku], [advertised_asin]",
        )

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
                    [page_views]
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

    def fetch_sku_cost_rows(
        self,
        *,
        marketplace_id: str,
        as_of_date: date,
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
                (marketplace_id, as_of_date, as_of_date),
            )
            return rows_to_dicts(cursor)
        finally:
            cursor.close()

    def fetch_settlement_advertising_summary(
        self,
        *,
        marketplace_id: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
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
                        [amount],
                        [currency],
                        [profit_bucket],
                        {posted_date_expression} AS [posted_date]
                    FROM dbo.[amazon_settlement_transaction]
                    WHERE [marketplace_id] = ?
                      AND [is_settlement_summary] = 0
                      AND [amount] IS NOT NULL
                      {currency_filter}
                )
                SELECT
                    COALESCE(SUM(CASE
                        WHEN [profit_bucket] = 'advertising_cost' THEN [amount]
                        ELSE 0
                    END), 0) AS [settlement_advertising_fee],
                    COUNT(1) AS [settlement_row_count],
                    MIN(NULLIF([currency], '')) AS [currency]
                FROM normalized
                WHERE [posted_date] >= ?
                  AND [posted_date] <= ?;
                """,
                params,
            )
            return one_row_to_dict(cursor)
        finally:
            cursor.close()

    def fetch_negative_keyword_rows(
        self,
        *,
        marketplace_id: str,
        profile_id: str | None,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Return existing negative keyword snapshot rows when a table/import is available.

        The current normalized schema does not yet persist Amazon Ads negative keywords,
        so the service also supports manual CSV rows via scripts. Keeping this method
        as a no-op preserves the repository contract without inventing a table.
        """

        _ = (marketplace_id, profile_id, start_date, end_date)
        return []

    def _fetch_ads_rows(
        self,
        *,
        table_name: str,
        columns: tuple[str, ...],
        marketplace_id: str,
        profile_id: str | None,
        start_date: date,
        end_date: date,
        order_by: str,
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
            column_sql = ",\n                    ".join(columns)
            cursor.execute(
                f"""
                SELECT
                    {column_sql}
                FROM dbo.[{table_name}]
                WHERE [marketplace_id] = ?
                  {where_profile}
                  AND [report_date] >= ?
                  AND [report_date] <= ?
                ORDER BY {order_by};
                """,
                params,
            )
            return rows_to_dicts(cursor)
        finally:
            cursor.close()


__all__ = ["WeeklyAdsOptimizationRepo"]
