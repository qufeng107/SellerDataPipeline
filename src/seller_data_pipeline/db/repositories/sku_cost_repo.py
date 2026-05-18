from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

SKU_COST_TABLE = "amazon_sku_cost"


@dataclass(frozen=True)
class SkuCandidateRecord:
    marketplace_id: str
    seller_sku: str
    asin: str | None = None
    product_name: str | None = None
    sku_sources: str = ""
    latest_source_date: date | None = None


@dataclass(frozen=True)
class SkuCostRecord:
    marketplace_id: str
    seller_sku: str
    asin: str | None
    product_cost: Decimal
    first_mile_cost: Decimal
    packaging_cost: Decimal
    other_unit_cost: Decimal
    currency: str
    effective_from: date
    effective_to: date | None = None
    remark: str | None = None
    updated_at: Any | None = None


@dataclass(frozen=True)
class SkuCostWriteRecord:
    marketplace_id: str
    seller_sku: str
    asin: str | None
    product_cost: Decimal
    first_mile_cost: Decimal
    packaging_cost: Decimal
    other_unit_cost: Decimal
    currency: str
    effective_from: date
    effective_to: date | None = None
    remark: str | None = None


class SkuCostRepo:
    """Azure SQL repository for SKU cost template export/import workflows."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def fetch_sku_candidates(self, *, marketplace_id: str) -> list[SkuCandidateRecord]:
        cursor = self.connection.cursor()
        try:
            cursor.execute(FETCH_SKU_CANDIDATES_SQL, (marketplace_id,) * 4)
            return [_row_to_sku_candidate(row) for row in cursor.fetchall()]
        finally:
            cursor.close()

    def fetch_latest_sku_costs(self, *, marketplace_id: str) -> dict[str, SkuCostRecord]:
        cursor = self.connection.cursor()
        try:
            cursor.execute(FETCH_LATEST_SKU_COSTS_SQL, (marketplace_id,))
            records = [_row_to_sku_cost(row) for row in cursor.fetchall()]
            return {record.seller_sku: record for record in records}
        finally:
            cursor.close()

    def sku_cost_exists(
        self,
        *,
        marketplace_id: str,
        seller_sku: str,
        effective_from: date,
    ) -> bool:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                SELECT COUNT_BIG(*)
                FROM dbo.[amazon_sku_cost]
                WHERE [marketplace_id] = ?
                  AND [seller_sku] = ?
                  AND [effective_from] = ?;
                """,
                (marketplace_id, seller_sku, effective_from),
            )
            row = cursor.fetchone()
            return bool(row and int(row[0]) > 0)
        finally:
            cursor.close()

    def close_previous_open_cost(
        self,
        *,
        marketplace_id: str,
        seller_sku: str,
        new_effective_from: date,
    ) -> int:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                UPDATE dbo.[amazon_sku_cost]
                SET [effective_to] = DATEADD(day, -1, ?),
                    [updated_at] = SYSUTCDATETIME()
                WHERE [marketplace_id] = ?
                  AND [seller_sku] = ?
                  AND [effective_to] IS NULL
                  AND [effective_from] < ?;
                """,
                (new_effective_from, marketplace_id, seller_sku, new_effective_from),
            )
            return int(getattr(cursor, "rowcount", 0) or 0)
        finally:
            cursor.close()

    def insert_sku_cost(self, record: SkuCostWriteRecord) -> None:
        cursor = self.connection.cursor()
        try:
            cursor.execute(INSERT_SKU_COST_SQL, _write_record_params(record))
        finally:
            cursor.close()

    def update_sku_cost(self, record: SkuCostWriteRecord) -> None:
        cursor = self.connection.cursor()
        try:
            cursor.execute(UPDATE_SKU_COST_SQL, _update_record_params(record))
        finally:
            cursor.close()

    def commit(self) -> None:
        self.connection.commit()


FETCH_SKU_CANDIDATES_SQL = """
WITH sku_sources AS (
    SELECT
        [marketplace_id],
        NULLIF(LTRIM(RTRIM([seller_sku])), '') AS [seller_sku],
        NULLIF(LTRIM(RTRIM([asin])), '') AS [asin],
        NULLIF(LTRIM(RTRIM([item_name])), '') AS [product_name],
        CAST([snapshot_date] AS date) AS [source_date],
        CAST('listing' AS nvarchar(40)) AS [source_name],
        CAST(1 AS int) AS [source_rank]
    FROM dbo.[amazon_listing_snapshot]
    WHERE [marketplace_id] = ?

    UNION ALL

    SELECT
        [marketplace_id],
        NULLIF(LTRIM(RTRIM([seller_sku])), '') AS [seller_sku],
        NULLIF(LTRIM(RTRIM([asin])), '') AS [asin],
        NULLIF(LTRIM(RTRIM([product_name])), '') AS [product_name],
        CAST([snapshot_date] AS date) AS [source_date],
        CAST('inventory' AS nvarchar(40)) AS [source_name],
        CAST(2 AS int) AS [source_rank]
    FROM dbo.[amazon_inventory_daily]
    WHERE [marketplace_id] = ?

    UNION ALL

    SELECT
        [marketplace_id],
        NULLIF(LTRIM(RTRIM([seller_sku])), '') AS [seller_sku],
        NULLIF(LTRIM(RTRIM([asin])), '') AS [asin],
        NULLIF(LTRIM(RTRIM([product_name])), '') AS [product_name],
        TRY_CONVERT(date, LEFT([purchase_date_raw], 10)) AS [source_date],
        CAST('orders' AS nvarchar(40)) AS [source_name],
        CAST(3 AS int) AS [source_rank]
    FROM dbo.[amazon_order_item]
    WHERE [marketplace_id] = ?

    UNION ALL

    SELECT
        [marketplace_id],
        NULLIF(LTRIM(RTRIM([seller_sku])), '') AS [seller_sku],
        NULL AS [asin],
        NULL AS [product_name],
        TRY_CONVERT(date, LEFT(COALESCE([posted_date_time_raw], [posted_date_raw]), 10))
            AS [source_date],
        CAST('settlement' AS nvarchar(40)) AS [source_name],
        CAST(4 AS int) AS [source_rank]
    FROM dbo.[amazon_settlement_transaction]
    WHERE [marketplace_id] = ?
),
clean_sources AS (
    SELECT *
    FROM sku_sources
    WHERE [seller_sku] IS NOT NULL
),
ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY [marketplace_id], [seller_sku]
            ORDER BY
                CASE WHEN [product_name] IS NULL THEN 1 ELSE 0 END,
                [source_rank] ASC,
                [source_date] DESC
        ) AS [rn]
    FROM clean_sources
),
source_summary AS (
    SELECT
        [marketplace_id],
        [seller_sku],
        MAX([source_date]) AS [latest_source_date],
        CONCAT_WS(
            ',',
            CASE WHEN MAX(CASE WHEN [source_name] = 'listing' THEN 1 ELSE 0 END) = 1
                THEN 'listing' END,
            CASE WHEN MAX(CASE WHEN [source_name] = 'inventory' THEN 1 ELSE 0 END) = 1
                THEN 'inventory' END,
            CASE WHEN MAX(CASE WHEN [source_name] = 'orders' THEN 1 ELSE 0 END) = 1
                THEN 'orders' END,
            CASE WHEN MAX(CASE WHEN [source_name] = 'settlement' THEN 1 ELSE 0 END) = 1
                THEN 'settlement' END
        ) AS [sku_sources]
    FROM clean_sources
    GROUP BY [marketplace_id], [seller_sku]
)
SELECT
    ranked.[marketplace_id],
    ranked.[seller_sku],
    ranked.[asin],
    ranked.[product_name],
    source_summary.[sku_sources],
    source_summary.[latest_source_date]
FROM ranked
INNER JOIN source_summary
    ON source_summary.[marketplace_id] = ranked.[marketplace_id]
   AND source_summary.[seller_sku] = ranked.[seller_sku]
WHERE ranked.[rn] = 1
ORDER BY ranked.[seller_sku];
"""

FETCH_LATEST_SKU_COSTS_SQL = """
WITH ranked AS (
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
        [remark],
        [updated_at],
        ROW_NUMBER() OVER (
            PARTITION BY [marketplace_id], [seller_sku]
            ORDER BY [effective_from] DESC, [id] DESC
        ) AS [rn]
    FROM dbo.[amazon_sku_cost]
    WHERE [marketplace_id] = ?
)
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
    [remark],
    [updated_at]
FROM ranked
WHERE [rn] = 1
ORDER BY [seller_sku];
"""

INSERT_SKU_COST_SQL = """
INSERT INTO dbo.[amazon_sku_cost] (
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
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

UPDATE_SKU_COST_SQL = """
UPDATE dbo.[amazon_sku_cost]
SET
    [asin] = ?,
    [product_cost] = ?,
    [first_mile_cost] = ?,
    [packaging_cost] = ?,
    [other_unit_cost] = ?,
    [currency] = ?,
    [effective_to] = ?,
    [remark] = ?,
    [updated_at] = SYSUTCDATETIME()
WHERE [marketplace_id] = ?
  AND [seller_sku] = ?
  AND [effective_from] = ?;
"""


def _row_to_sku_candidate(row: Any) -> SkuCandidateRecord:
    return SkuCandidateRecord(
        marketplace_id=str(row[0]),
        seller_sku=str(row[1]),
        asin=row[2],
        product_name=row[3],
        sku_sources=str(row[4] or ""),
        latest_source_date=row[5],
    )


def _row_to_sku_cost(row: Any) -> SkuCostRecord:
    return SkuCostRecord(
        marketplace_id=str(row[0]),
        seller_sku=str(row[1]),
        asin=row[2],
        product_cost=_decimal(row[3]),
        first_mile_cost=_decimal(row[4]),
        packaging_cost=_decimal(row[5]),
        other_unit_cost=_decimal(row[6]),
        currency=str(row[7]),
        effective_from=row[8],
        effective_to=row[9],
        remark=row[10],
        updated_at=row[11],
    )


def _write_record_params(record: SkuCostWriteRecord) -> tuple[Any, ...]:
    return (
        record.marketplace_id,
        record.seller_sku,
        record.asin,
        _db_decimal(record.product_cost),
        _db_decimal(record.first_mile_cost),
        _db_decimal(record.packaging_cost),
        _db_decimal(record.other_unit_cost),
        record.currency,
        record.effective_from,
        record.effective_to,
        record.remark,
    )


def _update_record_params(record: SkuCostWriteRecord) -> tuple[Any, ...]:
    return (
        record.asin,
        _db_decimal(record.product_cost),
        _db_decimal(record.first_mile_cost),
        _db_decimal(record.packaging_cost),
        _db_decimal(record.other_unit_cost),
        record.currency,
        record.effective_to,
        record.remark,
        record.marketplace_id,
        record.seller_sku,
        record.effective_from,
    )


def _decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value or "0"))


def _db_decimal(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.0001")))


__all__ = [
    "SkuCandidateRecord",
    "SkuCostRecord",
    "SkuCostRepo",
    "SkuCostWriteRecord",
]
