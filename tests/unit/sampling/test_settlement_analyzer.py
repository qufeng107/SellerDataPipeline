from __future__ import annotations

from pathlib import Path

from seller_data_pipeline.sampling.settlement_analyzer import (
    analyze_settlement_report_files,
    render_settlement_aggregate_markdown,
)

HEADER = "\t".join(
    [
        "settlement-id",
        "settlement-start-date",
        "settlement-end-date",
        "deposit-date",
        "total-amount",
        "currency",
        "transaction-type",
        "order-id",
        "merchant-order-id",
        "adjustment-id",
        "shipment-id",
        "marketplace-name",
        "amount-type",
        "amount-description",
        "amount",
        "fulfillment-id",
        "posted-date",
        "posted-date-time",
        "order-item-code",
        "merchant-order-item-id",
        "merchant-adjustment-item-id",
        "sku",
        "quantity-purchased",
        "promotion-id",
    ]
)


def test_settlement_aggregate_analysis_counts_classifications(tmp_path: Path) -> None:
    raw_file = tmp_path / "settlement.txt"
    raw_file.write_text(
        HEADER
        + "\n"
        + "\t".join(
            [
                "123",
                "2026-05-01 00:00:00 UTC",
                "2026-05-14 00:00:00 UTC",
                "2026-05-16 00:00:00 UTC",
                "99.50",
                "USD",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            ]
        )
        + "\n"
        + "\t".join(
            [
                "123",
                "",
                "",
                "",
                "",
                "",
                "Order",
                "111-2222222-3333333",
                "",
                "",
                "shipment-1",
                "Amazon.com",
                "ItemPrice",
                "Principal",
                "19.99",
                "AFN",
                "2026-05-10",
                "",
                "item-1",
                "",
                "",
                "SKU-1",
                "1",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    analysis = analyze_settlement_report_files(
        raw_file_paths=[raw_file],
        marketplace_id="ATVPDKIKX0DER",
    )

    assert analysis.row_count == 2
    assert analysis.summary_row_count == 1
    assert analysis.transaction_row_count == 1
    assert analysis.profit_bucket_counts["reconciliation"] == 1
    assert analysis.profit_bucket_counts["revenue"] == 1
    assert analysis.amount_category_counts["product_sales"] == 1

    markdown = render_settlement_aggregate_markdown(analysis)
    assert "GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2 聚合取样记录" in markdown
    assert "amazon_settlement_transaction" in markdown
    assert "product_sales" in markdown
