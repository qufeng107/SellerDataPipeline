from __future__ import annotations

from decimal import Decimal

from seller_data_pipeline.parsers.amazon.promotion_coupon_parser import (
    CouponPerformanceParser,
    PromotionPerformanceParser,
)

PROMOTION_JSON = """
{
  "reportSpecification": {
    "reportType": "GET_PROMOTION_PERFORMANCE_REPORT",
    "reportOptions": {
      "promotionStartDateFrom": "2026-02-14T00:00:00Z",
      "promotionStartDateTo": "2026-05-14T00:00:00Z"
    },
    "marketplaceIds": ["ATVPDKIKX0DER"]
  },
  "promotions": [
    {
      "promotionId": "P1",
      "promotionName": "Spring deal",
      "marketplaceId": "ATVPDKIKX0DER",
      "merchantId": "M1",
      "type": "BEST_DEAL",
      "status": "APPROVED",
      "glanceViews": 435,
      "unitsSold": 37,
      "revenue": 622.69,
      "revenueCurrencyCode": "USD",
      "startDateTime": "2026-03-23T07:00:00Z",
      "endDateTime": "2026-03-25T06:59:59Z",
      "createdDateTime": "2026-03-23T03:25:30Z",
      "lastUpdatedDateTime": "2026-05-09T00:00:00Z",
      "includedProducts": [
        {
          "asin": "B000000001",
          "productName": "Product 1",
          "productGlanceViews": 24,
          "productUnitsSold": 4,
          "productRevenue": 75.88,
          "productRevenueCurrencyCode": "USD"
        }
      ]
    }
  ]
}
"""

COUPON_JSON = """
{
  "reportSpecification": {
    "reportType": "GET_COUPON_PERFORMANCE_REPORT",
    "reportOptions": {
      "couponStartDateFrom": "2026-02-14T00:00:00Z",
      "couponStartDateTo": "2026-05-14T00:00:00Z"
    },
    "marketplaceIds": ["ATVPDKIKX0DER"]
  },
  "coupons": [
    {
      "couponId": "C1",
      "merchantId": "M1",
      "marketplaceId": "ATVPDKIKX0DER",
      "currencyCode": "USD",
      "name": "Save 30%",
      "websiteMessage": "Save 30% on Passport Holder",
      "startDateTime": "2026-03-25T07:00:00Z",
      "endDateTime": "2026-04-01T06:59:59Z",
      "discountType": "PERCENT_OFF_LIST_PRICE",
      "discountAmount": 30.0,
      "totalDiscount": 255.87,
      "clips": 113,
      "redemptions": 33,
      "budget": 600.0,
      "budgetSpent": 255.87,
      "budgetRemaining": 344.13,
      "budgetPercentageUsed": 42.645,
      "sales": 514.0,
      "asins": [{"asin": "B000000001"}, {"asin": "B000000002"}]
    }
  ]
}
"""


def test_promotion_parser_maps_promotion_and_product_rows() -> None:
    result = PromotionPerformanceParser().parse_text(
        text=PROMOTION_JSON,
        source_report_id="report-promo",
        source_raw_file_path="reports/raw/promo.txt",
    )

    assert len(result.promotions) == 1
    assert len(result.included_products) == 1
    promotion = result.promotions[0]
    assert promotion.marketplace_id == "ATVPDKIKX0DER"
    assert promotion.promotion_id == "P1"
    assert promotion.promotion_type == "BEST_DEAL"
    assert promotion.glance_views == 435
    assert promotion.units_sold == 37
    assert promotion.revenue == Decimal("622.69")
    assert promotion.to_dict()["revenue"] == "622.69"
    assert len(promotion.source_row_hash) == 64

    product = result.included_products[0]
    assert product.promotion_id == "P1"
    assert product.asin == "B000000001"
    assert product.product_units_sold == 4
    assert product.product_revenue == Decimal("75.88")
    assert product.to_dict()["product_revenue"] == "75.88"


def test_coupon_parser_maps_coupon_and_asin_rows() -> None:
    result = CouponPerformanceParser().parse_text(
        text=COUPON_JSON,
        source_report_id="report-coupon",
        source_raw_file_path="reports/raw/coupon.txt",
    )

    assert len(result.coupons) == 1
    assert len(result.coupon_asins) == 2
    coupon = result.coupons[0]
    assert coupon.marketplace_id == "ATVPDKIKX0DER"
    assert coupon.coupon_id == "C1"
    assert coupon.discount_type == "PERCENT_OFF_LIST_PRICE"
    assert coupon.discount_amount == Decimal("30.0")
    assert coupon.total_discount == Decimal("255.87")
    assert coupon.clips == 113
    assert coupon.redemptions == 33
    assert coupon.to_dict()["budget_spent"] == "255.87"
    assert len(coupon.source_row_hash) == 64

    asin_record = result.coupon_asins[0]
    assert asin_record.coupon_id == "C1"
    assert asin_record.asin == "B000000001"
    assert asin_record.currency_code == "USD"
