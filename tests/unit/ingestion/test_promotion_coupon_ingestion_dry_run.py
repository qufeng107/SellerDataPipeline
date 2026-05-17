from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from seller_data_pipeline.ingestion.promotion_coupon_ingestion_dry_run import (
    PromotionCouponIngestionDryRunService,
)
from seller_data_pipeline.parsers.amazon.promotion_coupon_parser import (
    COUPON_PERFORMANCE_REPORT_TYPE,
    PROMOTION_PERFORMANCE_REPORT_TYPE,
)

MARKETPLACE_ID = "ATVPDKIKX0DER"


def test_promotion_coupon_dry_run_uses_latest_valid_raw_files(tmp_path: Path) -> None:
    raw_root = tmp_path / "reports" / "raw"
    _write_promotion_raw(raw_root, report_id="promotion-1")
    _write_coupon_raw(raw_root, report_id="coupon-1")

    service = PromotionCouponIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=tmp_path / "runtime",
    )
    result = service.prepare(marketplace_id=MARKETPLACE_ID)

    assert result.status == "success"
    assert result.requires_review is False
    assert result.prepared_row_count == 4
    assert result.preview_file_count == 4
    table_counts: dict[str, int] = {}
    for report_result in result.report_results:
        table_counts.update(report_result.table_row_counts)
    assert table_counts["amazon_promotion_performance"] == 1
    assert table_counts["amazon_promotion_product_performance"] == 1
    assert table_counts["amazon_coupon_performance"] == 1
    assert table_counts["amazon_coupon_asin"] == 1


def test_promotion_coupon_dry_run_blocks_diagnostic_report(tmp_path: Path) -> None:
    raw_root = tmp_path / "reports" / "raw"
    promotion_path = _write_json_raw(
        raw_root,
        PROMOTION_PERFORMANCE_REPORT_TYPE,
        "promotion-diagnostic",
        {"diagnostic": "schema drift"},
    )
    _write_coupon_raw(raw_root, report_id="coupon-1")

    service = PromotionCouponIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=tmp_path / "runtime",
    )
    result = service.prepare(
        marketplace_id=MARKETPLACE_ID,
        promotion_raw_file_path=promotion_path,
    )

    assert result.requires_review is True
    assert result.status == "requires_review"


def _write_promotion_raw(root: Path, *, report_id: str) -> Path:
    payload = {
        "reportSpecification": {
            "reportType": PROMOTION_PERFORMANCE_REPORT_TYPE,
            "reportOptions": {
                "promotionStartDateFrom": "2026-05-01",
                "promotionStartDateTo": "2026-05-31",
            },
            "marketplaceIds": [MARKETPLACE_ID],
        },
        "promotions": [
            {
                "promotionId": "PROMO-1",
                "marketplaceId": MARKETPLACE_ID,
                "merchantId": "MERCHANT-1",
                "promotionName": "Prime Day Test Discount",
                "type": "PriceDiscount",
                "status": "Ended",
                "glanceViews": 100,
                "unitsSold": 3,
                "revenue": "59.97",
                "revenueCurrencyCode": "USD",
                "startDateTime": "2026-05-01T00:00:00Z",
                "endDateTime": "2026-05-07T23:59:59Z",
                "createdDateTime": "2026-04-25T00:00:00Z",
                "lastUpdatedDateTime": "2026-05-08T00:00:00Z",
                "includedProducts": [
                    {
                        "asin": "ASIN-1",
                        "productName": "Product 1",
                        "productGlanceViews": 40,
                        "productUnitsSold": 1,
                        "productRevenue": "19.99",
                        "productRevenueCurrencyCode": "USD",
                    }
                ],
            }
        ],
    }
    return _write_json_raw(root, PROMOTION_PERFORMANCE_REPORT_TYPE, report_id, payload)


def _write_coupon_raw(root: Path, *, report_id: str) -> Path:
    payload = {
        "reportSpecification": {
            "reportType": COUPON_PERFORMANCE_REPORT_TYPE,
            "reportOptions": {
                "couponStartDateFrom": "2026-05-01",
                "couponStartDateTo": "2026-05-31",
            },
            "marketplaceIds": [MARKETPLACE_ID],
        },
        "coupons": [
            {
                "couponId": "COUPON-1",
                "merchantId": "MERCHANT-1",
                "marketplaceId": MARKETPLACE_ID,
                "currencyCode": "USD",
                "name": "Fixed Coupon Test",
                "websiteMessage": "$2 off",
                "startDateTime": "2026-05-01T00:00:00Z",
                "endDateTime": "2026-05-07T23:59:59Z",
                "discountType": "MoneyOff",
                "discountAmount": "2.00",
                "totalDiscount": "4.00",
                "clips": 10,
                "redemptions": 2,
                "budget": "100.00",
                "budgetSpent": "4.00",
                "budgetRemaining": "96.00",
                "budgetPercentageUsed": "4.00",
                "sales": "39.98",
                "asins": [{"asin": "ASIN-1"}],
            }
        ],
    }
    return _write_json_raw(root, COUPON_PERFORMANCE_REPORT_TYPE, report_id, payload)


def _write_json_raw(
    root: Path,
    report_type: str,
    report_id: str,
    payload: dict[str, Any],
) -> Path:
    path = root / "amazon" / MARKETPLACE_ID / report_type / "2026-05-14" / f"{report_id}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
