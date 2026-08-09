from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from seller_data_pipeline.db.repositories.finance_repo import rows_to_dicts
from seller_data_pipeline.db.settlement_sql import settlement_date_sql


@dataclass(frozen=True)
class CoverageSourceSpec:
    data_domain: str
    source_table: str
    business_date_expression: str
    business_date_semantics: str
    entity_expression: str | None = None
    marketplace_column: str | None = "marketplace_id"
    notes: str = ""


CORE_COVERAGE_SOURCE_SPECS: tuple[CoverageSourceSpec, ...] = (
    CoverageSourceSpec(
        data_domain="Ads SP campaign daily",
        source_table="amazon_ads_sp_campaign_daily",
        business_date_expression="[report_date]",
        business_date_semantics="report_date",
        entity_expression="[campaign_id]",
        notes=(
            "Advertising spend/performance context; "
            "financial ad cost still reconciles to Settlement."
        ),
    ),
    CoverageSourceSpec(
        data_domain="Ads SP targeting daily",
        source_table="amazon_ads_sp_targeting_daily",
        business_date_expression="[report_date]",
        business_date_semantics="report_date",
        entity_expression="[keyword_id]",
        notes="Keyword/targeting optimization source.",
    ),
    CoverageSourceSpec(
        data_domain="Ads SP search term daily",
        source_table="amazon_ads_sp_search_term_daily",
        business_date_expression="[report_date]",
        business_date_semantics="report_date",
        entity_expression="[search_term]",
        notes="Search term optimization source.",
    ),
    CoverageSourceSpec(
        data_domain="Ads SP advertised product daily",
        source_table="amazon_ads_sp_advertised_product_daily",
        business_date_expression="[report_date]",
        business_date_semantics="report_date",
        entity_expression="[advertised_sku]",
        notes="Advertised SKU/ASIN ad performance source.",
    ),
    CoverageSourceSpec(
        data_domain="Listing snapshot",
        source_table="amazon_listing_snapshot",
        business_date_expression="[snapshot_date]",
        business_date_semantics="snapshot_date",
        entity_expression="[seller_sku]",
        notes="SKU/ASIN/listing state snapshot; not expected to have every calendar day.",
    ),
    CoverageSourceSpec(
        data_domain="Inventory snapshot",
        source_table="amazon_inventory_daily",
        business_date_expression="[snapshot_date]",
        business_date_semantics="snapshot_date",
        entity_expression="[seller_sku]",
        notes="Primary current FBA inventory balance source.",
    ),
    CoverageSourceSpec(
        data_domain="Sales & Traffic date daily",
        source_table="amazon_sales_traffic_daily",
        business_date_expression="[report_date]",
        business_date_semantics="report_date",
        entity_expression=None,
        notes="Store/date traffic and sales source.",
    ),
    CoverageSourceSpec(
        data_domain="Sales & Traffic ASIN daily",
        source_table="amazon_sales_traffic_asin_daily",
        business_date_expression="COALESCE([report_start_date], [report_end_date])",
        business_date_semantics="report_start_date/report_end_date",
        entity_expression="COALESCE([child_asin], [parent_asin])",
        notes="ASIN traffic and sales source.",
    ),
    CoverageSourceSpec(
        data_domain="Settlement transaction",
        source_table="amazon_settlement_transaction",
        business_date_expression=settlement_date_sql(
            "[posted_date_time_raw]", "[posted_date_raw]", "[deposit_date_raw]"
        ),
        business_date_semantics="posted_date/posted_date_time/deposit_date",
        entity_expression="[seller_sku]",
        notes="Financial source of truth for profit preview.",
    ),
    CoverageSourceSpec(
        data_domain="Orders",
        source_table="amazon_order_item",
        business_date_expression=(
            "COALESCE("
            "TRY_CONVERT(date, NULLIF([purchase_date_raw], ''), 127), "
            "TRY_CONVERT(date, NULLIF([purchase_date_raw], ''))"
            ")"
        ),
        business_date_semantics="purchase_date",
        entity_expression="[seller_sku]",
        notes="Operational SKU/order source; not the financial source of truth.",
    ),
    CoverageSourceSpec(
        data_domain="FBA reimbursements",
        source_table="amazon_fba_reimbursement",
        business_date_expression=(
            "COALESCE("
            "TRY_CONVERT(date, NULLIF([approval_date_raw], ''), 127), "
            "TRY_CONVERT(date, NULLIF([approval_date_raw], ''))"
            ")"
        ),
        business_date_semantics="approval_date",
        entity_expression="[seller_sku]",
        notes="FBA reimbursement/compensation audit source.",
    ),
    CoverageSourceSpec(
        data_domain="FBA fee preview",
        source_table="amazon_fba_fee_preview",
        business_date_expression="CONVERT(date, [created_at])",
        business_date_semantics="created_at snapshot date",
        entity_expression="[seller_sku]",
        notes="Snapshot-style estimated fee reference; final fees come from Settlement.",
    ),
    CoverageSourceSpec(
        data_domain="Promotion performance",
        source_table="amazon_promotion_performance",
        business_date_expression=(
            "COALESCE("
            "TRY_CONVERT(date, NULLIF([start_date_time_raw], ''), 127), "
            "TRY_CONVERT(date, NULLIF([start_date_time_raw], '')), "
            "TRY_CONVERT(date, NULLIF([created_date_time_raw], ''), 127), "
            "TRY_CONVERT(date, NULLIF([created_date_time_raw], ''))"
            ")"
        ),
        business_date_semantics="start_date_time/created_date_time",
        entity_expression="[promotion_id]",
        notes=(
            "Promotion configuration/effect source; "
            "financial deductions still reconcile to Settlement."
        ),
    ),
    CoverageSourceSpec(
        data_domain="Promotion product performance",
        source_table="amazon_promotion_product_performance",
        business_date_expression="CONVERT(date, [created_at])",
        business_date_semantics="created_at snapshot date",
        entity_expression="[asin]",
        notes=(
            "Promotion product detail has no event date column in current schema; "
            "created_at is used only as an ingestion snapshot indicator."
        ),
    ),
    CoverageSourceSpec(
        data_domain="Coupon performance",
        source_table="amazon_coupon_performance",
        business_date_expression=(
            "COALESCE("
            "TRY_CONVERT(date, NULLIF([start_date_time_raw], ''), 127), "
            "TRY_CONVERT(date, NULLIF([start_date_time_raw], ''))"
            ")"
        ),
        business_date_semantics="start_date_time",
        entity_expression="[coupon_id]",
        notes=(
            "Coupon configuration/effect source; "
            "financial deductions still reconcile to Settlement."
        ),
    ),
    CoverageSourceSpec(
        data_domain="Coupon ASIN",
        source_table="amazon_coupon_asin",
        business_date_expression=(
            "COALESCE("
            "TRY_CONVERT(date, NULLIF([start_date_time_raw], ''), 127), "
            "TRY_CONVERT(date, NULLIF([start_date_time_raw], ''))"
            ")"
        ),
        business_date_semantics="start_date_time",
        entity_expression="[asin]",
        notes="Coupon-ASIN mapping source.",
    ),
    CoverageSourceSpec(
        data_domain="Inventory ledger summary",
        source_table="amazon_inventory_ledger_summary_daily",
        business_date_expression=(
            "COALESCE("
            "TRY_CONVERT(date, NULLIF([ledger_date_raw], ''), 127), "
            "TRY_CONVERT(date, NULLIF([ledger_date_raw], ''))"
            ")"
        ),
        business_date_semantics="ledger_date",
        entity_expression="[seller_sku]",
        notes="Inventory movement/audit summary source.",
    ),
    CoverageSourceSpec(
        data_domain="Inventory ledger detail",
        source_table="amazon_inventory_ledger_detail",
        business_date_expression=(
            "COALESCE("
            "TRY_CONVERT(date, NULLIF([date_time_raw], ''), 127), "
            "TRY_CONVERT(date, NULLIF([date_time_raw], ''))"
            ")"
        ),
        business_date_semantics="date_time",
        entity_expression="[seller_sku]",
        notes="Inventory movement/audit detail source.",
    ),
    CoverageSourceSpec(
        data_domain="SKU cost",
        source_table="amazon_sku_cost",
        business_date_expression="[effective_from]",
        business_date_semantics="effective_from",
        entity_expression="[seller_sku]",
        notes="Internal standard cost coverage, not an Amazon data source.",
    ),
)


class DataCoverageRepo:
    """Read-only repository for normalized data coverage audits."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def fetch_core_coverage_rows(
        self,
        *,
        marketplace_id: str,
        target_start_date: date,
        target_end_date: date,
        specs: tuple[CoverageSourceSpec, ...] = CORE_COVERAGE_SOURCE_SPECS,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for spec in specs:
            row = self._fetch_one_coverage_row(
                spec=spec,
                marketplace_id=marketplace_id,
                target_start_date=target_start_date,
                target_end_date=target_end_date,
            )
            rows.append(row)
        return rows

    def _fetch_one_coverage_row(
        self,
        *,
        spec: CoverageSourceSpec,
        marketplace_id: str,
        target_start_date: date,
        target_end_date: date,
    ) -> dict[str, Any]:
        entity_expression = spec.entity_expression or "CAST(NULL AS NVARCHAR(4000))"
        marketplace_filter = "1 = 1"
        params: list[Any] = []
        if spec.marketplace_column:
            marketplace_filter = f"[{spec.marketplace_column}] = ?"
            params.append(marketplace_id)
        sql = f"""
            WITH normalized AS (
                SELECT
                    {spec.business_date_expression} AS [business_date],
                    CAST({entity_expression} AS NVARCHAR(4000)) AS [entity_key],
                    [created_at],
                    [updated_at]
                FROM dbo.[{spec.source_table}]
                WHERE {marketplace_filter}
            )
            SELECT
                COUNT_BIG(*) AS [row_count],
                SUM(CASE WHEN [business_date] IS NOT NULL THEN 1 ELSE 0 END)
                    AS [dated_row_count],
                MIN([business_date]) AS [min_business_date],
                MAX([business_date]) AS [max_business_date],
                COUNT(DISTINCT [business_date]) AS [distinct_business_dates],
                COUNT(DISTINCT NULLIF([entity_key], '')) AS [distinct_entity_count],
                SUM(CASE WHEN [business_date] >= ? AND [business_date] <= ? THEN 1 ELSE 0 END)
                    AS [target_window_row_count],
                MIN(
                    CASE
                        WHEN [business_date] >= ? AND [business_date] <= ?
                        THEN [business_date]
                    END
                ) AS [target_min_business_date],
                MAX(
                    CASE
                        WHEN [business_date] >= ? AND [business_date] <= ?
                        THEN [business_date]
                    END
                ) AS [target_max_business_date],
                MAX([created_at]) AS [latest_created_at],
                MAX([updated_at]) AS [latest_updated_at]
            FROM normalized;
        """
        params.extend(
            [
                target_start_date,
                target_end_date,
                target_start_date,
                target_end_date,
                target_start_date,
                target_end_date,
            ]
        )
        cursor = self.connection.cursor()
        try:
            cursor.execute(sql, tuple(params))
            row = rows_to_dicts(cursor)[0]
        finally:
            cursor.close()
        row.update(
            {
                "data_domain": spec.data_domain,
                "source_table": spec.source_table,
                "business_date_semantics": spec.business_date_semantics,
                "notes": spec.notes,
            }
        )
        return row

    def fetch_report_request_coverage_rows(
        self,
        *,
        marketplace_id: str,
        target_start_date: date,
        target_end_date: date,
    ) -> list[dict[str, Any]]:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    [source_system],
                    [report_type],
                    COUNT_BIG(*) AS [request_count],
                    SUM(CASE WHEN [processing_status] = 'DONE' THEN 1 ELSE 0 END)
                        AS [done_count],
                    SUM(CASE WHEN [download_status] = 'DOWNLOADED' THEN 1 ELSE 0 END)
                        AS [downloaded_count],
                    SUM(CASE WHEN [parse_status] = 'PARSED' THEN 1 ELSE 0 END)
                        AS [parsed_count],
                    MIN(CONVERT(date, [data_start_time])) AS [min_data_start_date],
                    MAX(CONVERT(date, [data_end_time])) AS [max_data_end_date],
                    SUM(
                        CASE
                            WHEN [data_end_time] >= ? AND [data_start_time] <= ? THEN 1
                            ELSE 0
                        END
                    ) AS [target_overlap_request_count],
                    MAX([requested_at]) AS [latest_requested_at],
                    MAX([downloaded_at]) AS [latest_downloaded_at],
                    MAX([parsed_at]) AS [latest_parsed_at]
                FROM dbo.[amazon_report_request]
                WHERE [marketplace_id] = ?
                GROUP BY [source_system], [report_type]
                ORDER BY [source_system], [report_type];
                """,
                (target_start_date, target_end_date, marketplace_id),
            )
            return rows_to_dicts(cursor)
        finally:
            cursor.close()


__all__ = [
    "CORE_COVERAGE_SOURCE_SPECS",
    "CoverageSourceSpec",
    "DataCoverageRepo",
]
