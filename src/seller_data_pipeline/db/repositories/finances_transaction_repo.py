from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from seller_data_pipeline.db.repositories.finance_repo import rows_to_dicts

TABLE_NAME = "amazon_finance_transaction"
COLUMNS = (
    "marketplace_id",
    "transaction_id",
    "transaction_status",
    "transaction_type",
    "description",
    "posted_at_utc",
    "posted_at_local",
    "posted_date_local",
    "marketplace_timezone",
    "amount",
    "currency",
    "settlement_id",
    "order_id",
    "deferred_transaction_id",
    "release_transaction_id",
    "management_role",
    "management_include",
    "management_replace_with_ads_api",
    "review_required",
    "product_sales_amount",
    "shipping_amount",
    "promotion_amount",
    "fba_fulfillment_fee",
    "shipping_chargeback",
    "refund_product_amount",
    "refund_shipping_amount",
    "refund_promotion_amount",
    "liquidation_revenue",
    "liquidation_fee",
    "subscription_fee",
    "coupon_fee",
    "deal_fee",
    "storage_fee",
    "customer_return_fee",
    "other_service_fee",
    "unit_events_json",
    "related_identifiers_json",
    "raw_transaction_json",
    "raw_transaction_hash",
    "business_key_hash",
)


@dataclass(frozen=True)
class FinancesUpsertResult:
    attempted_rows: int
    inserted_rows: int
    updated_rows: int
    skipped_rows: int

    @property
    def written_rows(self) -> int:
        return self.inserted_rows + self.updated_rows


class FinancesTransactionRepo:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def upsert_rows(self, rows: list[dict[str, Any]]) -> FinancesUpsertResult:
        sql = _merge_sql()
        inserted = 0
        updated = 0
        skipped = 0
        cursor = self.connection.cursor()
        try:
            for row in rows:
                if not row.get("transaction_id") or not row.get("business_key_hash"):
                    skipped += 1
                    continue
                params = tuple(_db_value(row.get(column)) for column in COLUMNS)
                cursor.execute(sql, params)
                action_row = cursor.fetchone()
                action = str(action_row[0]).upper() if action_row else "UPDATE"
                if action == "INSERT":
                    inserted += 1
                else:
                    updated += 1
        finally:
            cursor.close()
        return FinancesUpsertResult(
            attempted_rows=len(rows),
            inserted_rows=inserted,
            updated_rows=updated,
            skipped_rows=skipped,
        )

    def fetch_month_rows(
        self, *, marketplace_id: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    [marketplace_id], [transaction_id], [transaction_status],
                    [transaction_type], [description], [posted_at_utc], [posted_at_local],
                    [posted_date_local], [marketplace_timezone], [amount], [currency],
                    [settlement_id], [order_id], [deferred_transaction_id],
                    [release_transaction_id], [management_role], [management_include],
                    [management_replace_with_ads_api], [review_required],
                    [product_sales_amount], [shipping_amount], [promotion_amount],
                    [fba_fulfillment_fee], [shipping_chargeback], [refund_product_amount],
                    [refund_shipping_amount], [refund_promotion_amount],
                    [liquidation_revenue], [liquidation_fee], [subscription_fee],
                    [coupon_fee], [deal_fee], [storage_fee], [customer_return_fee],
                    [other_service_fee], [unit_events_json],
                    [related_identifiers_json], [raw_transaction_json],
                    [raw_transaction_hash], [business_key_hash]
                FROM dbo.[amazon_finance_transaction]
                WHERE [marketplace_id] = ?
                  AND [posted_date_local] >= ?
                  AND [posted_date_local] <= ?
                ORDER BY [posted_at_utc], [transaction_id];
                """,
                (marketplace_id, start_date, end_date),
            )
            return rows_to_dicts(cursor)
        finally:
            cursor.close()

    def commit(self) -> None:
        self.connection.commit()


def _merge_sql() -> str:
    source_select = ", ".join(f"? AS [{column}]" for column in COLUMNS)
    update_columns = [column for column in COLUMNS if column != "business_key_hash"]
    update_set = ",\n        ".join(
        f"target.[{column}] = source.[{column}]" for column in update_columns
    )
    insert_columns = ", ".join(f"[{column}]" for column in COLUMNS)
    insert_values = ", ".join(f"source.[{column}]" for column in COLUMNS)
    return (
        f"MERGE dbo.[{TABLE_NAME}] WITH (HOLDLOCK) AS target\n"
        f"USING (SELECT {source_select}) AS source\n"
        "ON target.[business_key_hash] = source.[business_key_hash]\n"
        "WHEN MATCHED THEN UPDATE SET\n        "
        + update_set
        + ",\n        target.[updated_at] = SYSUTCDATETIME()\n"
        "WHEN NOT MATCHED THEN INSERT ("
        + insert_columns
        + ") VALUES ("
        + insert_values
        + ")\nOUTPUT $action AS merge_action;"
    )


def _db_value(value: Any) -> Any:
    if isinstance(value, bool):
        return 1 if value else 0
    return value


__all__ = ["FinancesTransactionRepo", "FinancesUpsertResult", "TABLE_NAME"]
