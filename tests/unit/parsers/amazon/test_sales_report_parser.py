from __future__ import annotations

from decimal import Decimal

from seller_data_pipeline.parsers.amazon.sales_report_parser import SalesReportParser


SALES_REPORT_JSON = """
{
  "reportSpecification": {
    "reportType": "GET_SALES_AND_TRAFFIC_REPORT",
    "reportOptions": {
      "dateGranularity": "DAY",
      "asinGranularity": "PARENT"
    },
    "dataStartTime": "2026-05-07",
    "dataEndTime": "2026-05-14",
    "marketplaceIds": ["ATVPDKIKX0DER"]
  },
  "salesAndTrafficByDate": [
    {
      "date": "2026-05-14",
      "salesByDate": {
        "orderedProductSales": {"amount": 12.34, "currencyCode": "USD"},
        "orderedProductSalesB2B": {"amount": 0.00, "currencyCode": "USD"},
        "unitsOrdered": 2,
        "unitsOrderedB2B": 0,
        "totalOrderItems": 1,
        "totalOrderItemsB2B": 0,
        "averageSalesPerOrderItem": {"amount": 12.34, "currencyCode": "USD"},
        "averageSalesPerOrderItemB2B": {"amount": 0.00, "currencyCode": "USD"},
        "averageUnitsPerOrderItem": 2.0,
        "averageUnitsPerOrderItemB2B": 0.0,
        "averageSellingPrice": {"amount": 6.17, "currencyCode": "USD"},
        "averageSellingPriceB2B": {"amount": 0.00, "currencyCode": "USD"},
        "unitsRefunded": 0,
        "refundRate": 0.0,
        "claimsGranted": 0,
        "claimsAmount": {"amount": 0.00, "currencyCode": "USD"},
        "shippedProductSales": {"amount": 12.34, "currencyCode": "USD"},
        "unitsShipped": 2,
        "ordersShipped": 1
      },
      "trafficByDate": {
        "browserPageViews": 3,
        "mobileAppPageViews": 4,
        "pageViews": 7,
        "browserSessions": 2,
        "mobileAppSessions": 3,
        "sessions": 5,
        "buyBoxPercentage": 100.0,
        "orderItemSessionPercentage": 20.0,
        "unitSessionPercentage": 40.0,
        "averageOfferCount": 1,
        "averageParentItems": 1,
        "feedbackReceived": 0,
        "negativeFeedbackReceived": 0,
        "receivedNegativeFeedbackRate": 0.0
      }
    }
  ],
  "salesAndTrafficByAsin": [
    {
      "parentAsin": "B000000001",
      "salesByAsin": {
        "unitsOrdered": 19,
        "unitsOrderedB2B": 1,
        "orderedProductSales": {"amount": 477.0, "currencyCode": "USD"},
        "orderedProductSalesB2B": {"amount": 26.0, "currencyCode": "USD"},
        "totalOrderItems": 19,
        "totalOrderItemsB2B": 1
      },
      "trafficByAsin": {
        "browserSessions": 127,
        "browserSessionsB2B": 5,
        "mobileAppSessions": 222,
        "mobileAppSessionsB2B": 0,
        "sessions": 349,
        "sessionsB2B": 5,
        "browserSessionPercentage": 100.0,
        "browserSessionPercentageB2B": 100.0,
        "mobileAppSessionPercentage": 100.0,
        "mobileAppSessionPercentageB2B": 0.0,
        "sessionPercentage": 100.0,
        "sessionPercentageB2B": 100.0,
        "browserPageViews": 160,
        "browserPageViewsB2B": 5,
        "mobileAppPageViews": 341,
        "mobileAppPageViewsB2B": 0,
        "pageViews": 501,
        "pageViewsB2B": 5,
        "browserPageViewsPercentage": 100.0,
        "browserPageViewsPercentageB2B": 100.0,
        "mobileAppPageViewsPercentage": 100.0,
        "mobileAppPageViewsPercentageB2B": 0.0,
        "pageViewsPercentage": 100.0,
        "pageViewsPercentageB2B": 100.0,
        "buyBoxPercentage": 100.0,
        "buyBoxPercentageB2B": 100.0,
        "unitSessionPercentage": 5.44,
        "unitSessionPercentageB2B": 20.0
      }
    }
  ]
}
"""


def test_sales_report_parser_maps_date_level_metrics() -> None:
    result = SalesReportParser().parse_text(
        text=SALES_REPORT_JSON,
        source_report_id="report-3",
        source_raw_file_path="reports/raw/report-3.txt",
    )

    assert len(result.by_date) == 1
    record = result.by_date[0]
    assert record.marketplace_id == "ATVPDKIKX0DER"
    assert record.report_date == "2026-05-14"
    assert record.date_granularity == "DAY"
    assert record.asin_granularity == "PARENT"
    assert record.ordered_product_sales_amount == Decimal("12.34")
    assert record.ordered_product_sales_currency == "USD"
    assert record.ordered_product_sales_b2b_currency == "USD"
    assert record.average_sales_per_order_item_b2b_amount == Decimal("0.0")
    assert record.average_selling_price_currency == "USD"
    assert record.claims_amount_currency == "USD"
    assert record.units_ordered == 2
    assert record.total_order_items == 1
    assert record.sessions == 5
    assert record.unit_session_percentage == Decimal("40.0")
    assert record.source_report_type == "GET_SALES_AND_TRAFFIC_REPORT"
    assert len(record.source_row_hash) == 64
    assert record.to_dict()["ordered_product_sales_amount"] == "12.34"


def test_sales_report_parser_maps_asin_level_metrics() -> None:
    result = SalesReportParser().parse_text(text=SALES_REPORT_JSON)

    assert len(result.by_asin) == 1
    record = result.by_asin[0]
    assert record.parent_asin == "B000000001"
    assert record.child_asin is None
    assert record.report_start_date == "2026-05-07"
    assert record.report_end_date == "2026-05-14"
    assert record.ordered_product_sales_amount == Decimal("477.0")
    assert record.ordered_product_sales_b2b_amount == Decimal("26.0")
    assert record.ordered_product_sales_currency == "USD"
    assert record.units_ordered == 19
    assert record.units_ordered_b2b == 1
    assert record.total_order_items == 19
    assert record.total_order_items_b2b == 1
    assert record.sessions == 349
    assert record.sessions_b2b == 5
    assert record.page_views == 501
    assert record.page_views_percentage == Decimal("100.0")
    assert record.unit_session_percentage == Decimal("5.44")
    assert record.unit_session_percentage_b2b == Decimal("20.0")
    assert len(record.source_row_hash) == 64


def test_sales_report_parser_parse_returns_date_dicts() -> None:
    records = SalesReportParser().parse(SALES_REPORT_JSON)

    assert len(records) == 1
    assert records[0]["report_date"] == "2026-05-14"
