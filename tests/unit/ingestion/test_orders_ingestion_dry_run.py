from __future__ import annotations

import json
from pathlib import Path

from seller_data_pipeline.ingestion.orders_ingestion_dry_run import OrdersIngestionDryRunService

ORDERS_CONTENT = (
    "amazon-order-id\tmerchant-order-id\tpurchase-date\tlast-updated-date\torder-status\t"
    "fulfillment-channel\tsales-channel\torder-channel\tship-service-level\tproduct-name\t"
    "sku\tasin\titem-status\tquantity\tcurrency\titem-price\titem-tax\tshipping-price\t"
    "shipping-tax\tgift-wrap-price\tgift-wrap-tax\titem-promotion-discount\t"
    "ship-promotion-discount\tship-city\tship-state\tship-postal-code\tship-country\t"
    "promotion-ids\tcpf\tis-business-order\tpurchase-order-number\tprice-designation\t"
    "signature-confirmation-recommended\n"
    "ORDER-1\tMERCHANT-1\t2026-05-08T23:36:26+00:00\t2026-05-09T01:00:00+00:00\t"
    "Shipped\tAmazon\tAmazon.com\t\tStandard\tTravel Wallet\tSKU-1\tB000TEST\tShipped\t2\t"
    "USD\t20.00\t1.20\t4.99\t0.30\t\t\t-2.00\t0.00\tReading\tCA\t90001\tUS\t"
    "PROMO-1\t\tfalse\t\t\tfalse\n"
)


def _write_orders_raw(
    root: Path,
    marketplace_id: str,
    report_id: str,
    payload: str = ORDERS_CONTENT,
) -> Path:
    path = (
        root
        / "amazon"
        / marketplace_id
        / "GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL"
        / "2026-05-14"
        / f"{report_id}.txt"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return path


def test_orders_ingestion_dry_run_writes_preview_and_audit(tmp_path: Path) -> None:
    raw_root = tmp_path / "reports" / "raw"
    output_root = tmp_path / "runtime" / "ingestion" / "sp_api"
    _write_orders_raw(raw_root, "ATVPDKIKX0DER", "orders-report-1")

    result = OrdersIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=output_root,
    ).prepare(marketplace_id="ATVPDKIKX0DER")

    assert result.status == "success"
    assert result.processed_file_count == 1
    assert result.prepared_row_count == 1
    assert result.preview_file_count == 1
    summary_path = Path(result.output_dir) / "orders_ingestion_summary.json"
    audit_path = Path(result.output_dir) / "task_audit_event.json"
    schema_events_path = Path(result.output_dir) / "schema_validation_events.jsonl"
    assert summary_path.exists()
    assert audit_path.exists()
    assert schema_events_path.exists()
    preview_path = Path(result.report_result.preview_file_path or "")
    preview_rows = [
        json.loads(line) for line in preview_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(preview_rows) == 1
    assert preview_rows[0]["amazon_order_id"] == "ORDER-1"
    assert preview_rows[0]["business_key_hash"]
    assert preview_rows[0]["source_row_index"] == 1


def test_orders_ingestion_dry_run_blocks_non_empty_cpf(tmp_path: Path) -> None:
    raw_root = tmp_path / "reports" / "raw"
    _write_orders_raw(
        raw_root,
        "ATVPDKIKX0DER",
        "orders-report-1",
        ORDERS_CONTENT.replace("PROMO-1\t\tfalse", "PROMO-1\t123456789\tfalse"),
    )

    result = OrdersIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=tmp_path / "out",
    ).prepare(marketplace_id="ATVPDKIKX0DER")

    assert result.status == "requires_review"
    assert result.requires_review is True
    assert result.report_result.skipped is True
    assert result.report_result.skip_reason == "cpf_non_empty_requires_review"
    assert result.prepared_row_count == 0
    event = result.report_result.schema_validation_event or {}
    assert event["validation_status"] == "privacy_review_required"


def test_orders_ingestion_dry_run_blocks_schema_drift(tmp_path: Path) -> None:
    raw_root = tmp_path / "reports" / "raw"
    _write_orders_raw(
        raw_root,
        "ATVPDKIKX0DER",
        "orders-report-1",
        "amazon-order-id\tunexpected\nORDER-1\tvalue\n",
    )

    result = OrdersIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=tmp_path / "out",
    ).prepare(marketplace_id="ATVPDKIKX0DER")

    assert result.status == "requires_review"
    assert result.requires_review is True
    assert result.report_result.skipped is True
    assert result.report_result.skip_reason == "schema_validation_requires_review"
    assert result.prepared_row_count == 0
