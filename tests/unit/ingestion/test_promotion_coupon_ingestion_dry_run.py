from pathlib import Path

from seller_data_pipeline.ingestion.promotion_coupon_ingestion_dry_run import (
    PromotionCouponIngestionDryRunService,
)


def test_promotion_coupon_dry_run_uses_latest_valid_raw_files(tmp_path: Path) -> None:
    service = PromotionCouponIngestionDryRunService(
        raw_reports_root="reports/raw",
        output_root=tmp_path,
    )
    result = service.prepare(marketplace_id="ATVPDKIKX0DER")
    assert result.status == "success"
    assert result.requires_review is False
    assert result.prepared_row_count == 10
    assert result.preview_file_count == 4
    table_counts = {}
    for report_result in result.report_results:
        table_counts.update(report_result.table_row_counts)
    assert table_counts["amazon_promotion_performance"] == 1
    assert table_counts["amazon_promotion_product_performance"] == 3
    assert table_counts["amazon_coupon_performance"] == 2
    assert table_counts["amazon_coupon_asin"] == 4


def test_promotion_coupon_dry_run_blocks_diagnostic_report(tmp_path: Path) -> None:
    service = PromotionCouponIngestionDryRunService(
        raw_reports_root="reports/raw",
        output_root=tmp_path,
    )
    result = service.prepare(
        marketplace_id="ATVPDKIKX0DER",
        promotion_raw_file_path=(
            "reports/raw/amazon/ATVPDKIKX0DER/GET_PROMOTION_PERFORMANCE_REPORT/"
            "2026-05-14/112474020587.txt"
        ),
    )
    assert result.requires_review is True
    assert result.status == "requires_review"
