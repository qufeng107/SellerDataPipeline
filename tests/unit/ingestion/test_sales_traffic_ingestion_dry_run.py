from __future__ import annotations

import json
from pathlib import Path

from seller_data_pipeline.ingestion.sales_traffic_ingestion_dry_run import (
    SalesTrafficIngestionDryRunService,
)

SALES_TRAFFIC_PAYLOAD = {
    "reportSpecification": {
        "reportType": "GET_SALES_AND_TRAFFIC_REPORT",
        "dataStartTime": "2026-05-07",
        "dataEndTime": "2026-05-14",
        "marketplaceIds": ["ATVPDKIKX0DER"],
        "reportOptions": {"dateGranularity": "DAY", "asinGranularity": "PARENT"},
    },
    "salesAndTrafficByDate": [
        {
            "date": "2026-05-07",
            "salesByDate": {
                "orderedProductSales": {"amount": 100.0, "currencyCode": "USD"},
                "orderedProductSalesB2B": {"amount": 0.0, "currencyCode": "USD"},
                "unitsOrdered": 4,
                "unitsOrderedB2B": 0,
                "totalOrderItems": 4,
                "totalOrderItemsB2B": 0,
                "averageSalesPerOrderItem": {"amount": 25.0, "currencyCode": "USD"},
                "averageSalesPerOrderItemB2B": {"amount": 0.0, "currencyCode": "USD"},
                "averageUnitsPerOrderItem": 1.0,
                "averageUnitsPerOrderItemB2B": 0.0,
                "averageSellingPrice": {"amount": 25.0, "currencyCode": "USD"},
                "averageSellingPriceB2B": {"amount": 0.0, "currencyCode": "USD"},
                "unitsRefunded": 1,
                "refundRate": 25.0,
                "claimsGranted": 0,
                "claimsAmount": {"amount": 0.0, "currencyCode": "USD"},
                "shippedProductSales": {"amount": 126.0, "currencyCode": "USD"},
                "unitsShipped": 5,
                "ordersShipped": 5,
            },
            "trafficByDate": {
                "browserPageViews": 28,
                "browserPageViewsB2B": 2,
                "mobileAppPageViews": 48,
                "mobileAppPageViewsB2B": 0,
                "pageViews": 76,
                "pageViewsB2B": 2,
                "browserSessions": 20,
                "browserSessionsB2B": 2,
                "mobileAppSessions": 32,
                "mobileAppSessionsB2B": 0,
                "sessions": 52,
                "sessionsB2B": 2,
                "buyBoxPercentage": 100.0,
                "buyBoxPercentageB2B": 0.0,
                "orderItemSessionPercentage": 7.69,
                "orderItemSessionPercentageB2B": 0.0,
                "unitSessionPercentage": 7.69,
                "unitSessionPercentageB2B": 0.0,
                "averageOfferCount": 4,
                "averageParentItems": 1,
                "feedbackReceived": 1,
                "negativeFeedbackReceived": 0,
                "receivedNegativeFeedbackRate": 0.0,
            },
        }
    ],
    "salesAndTrafficByAsin": [
        {
            "parentAsin": "B000TEST01",
            "salesByAsin": {
                "orderedProductSales": {"amount": 100.0, "currencyCode": "USD"},
                "orderedProductSalesB2B": {"amount": 0.0, "currencyCode": "USD"},
                "unitsOrdered": 4,
                "unitsOrderedB2B": 0,
                "totalOrderItems": 4,
                "totalOrderItemsB2B": 0,
            },
            "trafficByAsin": {
                "browserPageViews": 28,
                "browserPageViewsB2B": 2,
                "browserPageViewsPercentage": 36.84,
                "browserPageViewsPercentageB2B": 100.0,
                "mobileAppPageViews": 48,
                "mobileAppPageViewsB2B": 0,
                "mobileAppPageViewsPercentage": 63.16,
                "mobileAppPageViewsPercentageB2B": 0.0,
                "pageViews": 76,
                "pageViewsB2B": 2,
                "pageViewsPercentage": 100.0,
                "pageViewsPercentageB2B": 100.0,
                "browserSessions": 20,
                "browserSessionsB2B": 2,
                "browserSessionPercentage": 38.46,
                "browserSessionPercentageB2B": 100.0,
                "mobileAppSessions": 32,
                "mobileAppSessionsB2B": 0,
                "mobileAppSessionPercentage": 61.54,
                "mobileAppSessionPercentageB2B": 0.0,
                "sessions": 52,
                "sessionsB2B": 2,
                "sessionPercentage": 100.0,
                "sessionPercentageB2B": 100.0,
                "buyBoxPercentage": 100.0,
                "buyBoxPercentageB2B": 0.0,
                "unitSessionPercentage": 7.69,
                "unitSessionPercentageB2B": 0.0,
            },
        }
    ],
}


def _write_sales_raw(
    root: Path, marketplace_id: str, report_id: str, payload: dict = SALES_TRAFFIC_PAYLOAD
) -> Path:
    path = (
        root
        / "amazon"
        / marketplace_id
        / "GET_SALES_AND_TRAFFIC_REPORT"
        / "2026-05-14"
        / f"{report_id}.txt"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_sales_traffic_dry_run_writes_two_previews_and_audit(tmp_path: Path) -> None:
    raw_root = tmp_path / "reports" / "raw"
    output_root = tmp_path / "runtime" / "ingestion" / "sp_api"
    _write_sales_raw(raw_root, "ATVPDKIKX0DER", "sales-report-1")

    result = SalesTrafficIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=output_root,
    ).prepare(marketplace_id="ATVPDKIKX0DER")

    assert result.status == "success"
    assert result.processed_file_count == 1
    assert result.prepared_row_count == 2
    assert result.preview_file_count == 2
    assert result.report_start_date == "2026-05-07"
    assert result.report_end_date == "2026-05-14"
    assert Path(result.output_dir, "sales_traffic_ingestion_summary.json").exists()
    assert Path(result.output_dir, "task_audit_event.json").exists()
    assert Path(result.output_dir, "schema_validation_events.jsonl").exists()
    daily_result = next(
        item for item in result.table_results if item.target_table == "amazon_sales_traffic_daily"
    )
    asin_result = next(
        item
        for item in result.table_results
        if item.target_table == "amazon_sales_traffic_asin_daily"
    )
    daily_row = json.loads(Path(daily_result.preview_file_path or "").read_text().splitlines()[0])
    asin_row = json.loads(Path(asin_result.preview_file_path or "").read_text().splitlines()[0])
    assert daily_row["marketplace_id"] == "ATVPDKIKX0DER"
    assert daily_row["report_date"] == "2026-05-07"
    assert daily_row["business_key_hash"]
    assert asin_row["parent_asin"] == "B000TEST01"
    assert asin_row["business_key_hash"]


def test_sales_traffic_dry_run_blocks_schema_drift(tmp_path: Path) -> None:
    raw_root = tmp_path / "reports" / "raw"
    _write_sales_raw(
        raw_root,
        "ATVPDKIKX0DER",
        "sales-report-1",
        {"unexpected": []},
    )

    result = SalesTrafficIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=tmp_path / "out",
    ).prepare(marketplace_id="ATVPDKIKX0DER")

    assert result.status == "requires_review"
    assert result.requires_review is True
    assert all(item.skipped for item in result.table_results)
    assert all(
        item.skip_reason == "schema_validation_requires_review" for item in result.table_results
    )
    assert result.prepared_row_count == 0
