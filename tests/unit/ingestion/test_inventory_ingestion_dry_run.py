from __future__ import annotations

import json
from pathlib import Path

from seller_data_pipeline.ingestion.inventory_ingestion_dry_run import (
    InventoryIngestionDryRunService,
    infer_snapshot_date_from_path,
)

INVENTORY_CONTENT = (
    "sku\tfnsku\tasin\tproduct-name\tcondition\tyour-price\tmfn-listing-exists\t"
    "mfn-fulfillable-quantity\tafn-listing-exists\tafn-warehouse-quantity\t"
    "afn-fulfillable-quantity\tafn-unsellable-quantity\tafn-reserved-quantity\t"
    "afn-total-quantity\tper-unit-volume\tafn-inbound-working-quantity\t"
    "afn-inbound-shipped-quantity\tafn-inbound-receiving-quantity\t"
    "afn-researching-quantity\tafn-reserved-future-supply\t"
    "afn-future-supply-buyable\tstore\n"
    "SKU-1\tFNSKU-1\tB000TEST01\tTest Product\tNew\t26.00\tNo\t\tYes\t"
    "284\t277\t1\t6\t284\t0.03\t0\t0\t0\t0\t0\t0\t\n"
)


def _write_inventory_raw(
    root: Path,
    marketplace_id: str,
    report_id: str,
    payload: str = INVENTORY_CONTENT,
) -> Path:
    path = (
        root
        / "amazon"
        / marketplace_id
        / "GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA"
        / "2026-05-14"
        / f"{report_id}.txt"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload.encode("cp1252"))
    return path


def test_inventory_ingestion_dry_run_writes_preview_and_audit(tmp_path: Path) -> None:
    raw_root = tmp_path / "reports" / "raw"
    output_root = tmp_path / "runtime" / "ingestion" / "sp_api"
    _write_inventory_raw(raw_root, "ATVPDKIKX0DER", "inventory-report-1")

    result = InventoryIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=output_root,
    ).prepare(marketplace_id="ATVPDKIKX0DER")

    assert result.status == "success"
    assert result.processed_file_count == 1
    assert result.prepared_row_count == 1
    assert result.preview_file_count == 1
    assert result.report_result.snapshot_date == "2026-05-14"
    summary_path = Path(result.output_dir) / "inventory_ingestion_summary.json"
    audit_path = Path(result.output_dir) / "task_audit_event.json"
    schema_events_path = Path(result.output_dir) / "schema_validation_events.jsonl"
    assert summary_path.exists()
    assert audit_path.exists()
    assert schema_events_path.exists()
    preview_path = Path(result.report_result.preview_file_path or "")
    preview_row = json.loads(preview_path.read_text(encoding="utf-8").splitlines()[0])
    assert preview_row["marketplace_id"] == "ATVPDKIKX0DER"
    assert preview_row["snapshot_date"] == "2026-05-14"
    assert preview_row["business_key_hash"]
    assert preview_row["afn_fulfillable_quantity"] == 277


def test_inventory_ingestion_dry_run_blocks_schema_drift(tmp_path: Path) -> None:
    raw_root = tmp_path / "reports" / "raw"
    _write_inventory_raw(
        raw_root,
        "ATVPDKIKX0DER",
        "inventory-report-1",
        "sku\tunexpected\nSKU-1\tvalue\n",
    )

    result = InventoryIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=tmp_path / "out",
    ).prepare(marketplace_id="ATVPDKIKX0DER")

    assert result.status == "requires_review"
    assert result.requires_review is True
    assert result.report_result.skipped is True
    assert result.report_result.skip_reason == "schema_validation_requires_review"
    assert result.report_result.prepared_row_count == 0


def test_infer_snapshot_date_from_path_uses_date_directory(tmp_path: Path) -> None:
    path = tmp_path / "amazon" / "ATVPDKIKX0DER" / "report" / "2026-05-14" / "1.txt"
    assert infer_snapshot_date_from_path(path).isoformat() == "2026-05-14"


def test_inventory_dry_run_allows_2026_08_03_additive_schema_drift(tmp_path: Path) -> None:
    raw_root = tmp_path / "reports" / "raw"
    payload = (
        "sku\tafn-fulfillable-quantity\tafn-fc-transfer-quantity\tafn-onhand-buyable-quantity\n"
        "SKU-1\t277\t3\t274\n"
    )
    _write_inventory_raw(raw_root, "ATVPDKIKX0DER", "inventory-report-aug-03", payload)

    result = InventoryIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=tmp_path / "out",
    ).prepare(marketplace_id="ATVPDKIKX0DER")

    assert result.status == "success"
    assert result.requires_review is False
    assert result.prepared_row_count == 1
    assert result.report_result.schema_validation_status == "new_fields"
    assert result.report_result.schema_validation_event is not None
    event = result.report_result.schema_validation_event
    assert event["requires_review"] is False
    assert json.loads(event["new_fields_json"]) == [
        "afn-fc-transfer-quantity",
        "afn-onhand-buyable-quantity",
    ]
    preview_row = json.loads(
        Path(result.report_result.preview_file_path or "").read_text().splitlines()[0]
    )
    raw_data = json.loads(preview_row["raw_data"])
    assert raw_data["afn-fc-transfer-quantity"] == "3"
    assert raw_data["afn-onhand-buyable-quantity"] == "274"


def test_inventory_dry_run_allows_optional_columns_to_be_absent(tmp_path: Path) -> None:
    raw_root = tmp_path / "reports" / "raw"
    _write_inventory_raw(
        raw_root,
        "ATVPDKIKX0DER",
        "inventory-report-minimal",
        "sku\tafn-fulfillable-quantity\nSKU-1\t277\n",
    )

    result = InventoryIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=tmp_path / "out",
    ).prepare(marketplace_id="ATVPDKIKX0DER")

    assert result.status == "success"
    assert result.requires_review is False
    assert result.prepared_row_count == 1
    assert result.report_result.schema_validation_status == "ok"


def test_inventory_dry_run_blocks_missing_required_sku(tmp_path: Path) -> None:
    raw_root = tmp_path / "reports" / "raw"
    _write_inventory_raw(
        raw_root,
        "ATVPDKIKX0DER",
        "inventory-report-missing-sku",
        "afn-fulfillable-quantity\tasin\n277\tB000TEST01\n",
    )

    result = InventoryIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=tmp_path / "out",
    ).prepare(marketplace_id="ATVPDKIKX0DER")

    assert result.status == "requires_review"
    assert result.requires_review is True
    assert result.report_result.schema_validation_status == "missing_fields"
    assert result.report_result.prepared_row_count == 0
