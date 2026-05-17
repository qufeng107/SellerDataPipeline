from __future__ import annotations

import json
from pathlib import Path

from seller_data_pipeline.ingestion.fba_reimbursements_ingestion_dry_run import (
    FbaReimbursementsIngestionDryRunService,
)

FBA_REIMBURSEMENTS_CONTENT = (
    "approval-date\treimbursement-id\tcase-id\tamazon-order-id\treason\tsku\tfnsku\tasin\t"
    "product-name\tcondition\tcurrency-unit\tamount-per-unit\tamount-total\t"
    "quantity-reimbursed-cash\tquantity-reimbursed-inventory\tquantity-reimbursed-total\t"
    "original-reimbursement-id\toriginal-reimbursement-type\n"
    "2026-05-10T01:02:03+00:00\tR-1\tCASE-1\tORDER-1\tCustomerReturn\tSKU-1\tFNSKU-1\t"
    "B000TEST\tTravel Wallet\tNewItem\tUSD\t10.00\t20.00\t2\t0\t2\t\t\n"
)


def _write_fba_reimbursements_raw(
    root: Path,
    marketplace_id: str,
    report_id: str,
    payload: str = FBA_REIMBURSEMENTS_CONTENT,
) -> Path:
    path = (
        root
        / "amazon"
        / marketplace_id
        / "GET_FBA_REIMBURSEMENTS_DATA"
        / "2026-05-14"
        / f"{report_id}.txt"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return path


def test_fba_reimbursements_ingestion_dry_run_writes_preview_and_audit(tmp_path: Path) -> None:
    raw_root = tmp_path / "reports" / "raw"
    output_root = tmp_path / "runtime" / "ingestion" / "sp_api"
    _write_fba_reimbursements_raw(raw_root, "ATVPDKIKX0DER", "fba-reimbursements-report-1")

    result = FbaReimbursementsIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=output_root,
    ).prepare(marketplace_id="ATVPDKIKX0DER")

    assert result.status == "success"
    assert result.processed_file_count == 1
    assert result.prepared_row_count == 1
    assert result.preview_file_count == 1
    summary_path = Path(result.output_dir) / "fba_reimbursements_ingestion_summary.json"
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
    assert preview_rows[0]["reimbursement_id"] == "R-1"
    assert preview_rows[0]["business_key_hash"]
    assert preview_rows[0]["source_row_index"] == 1


def test_fba_reimbursements_ingestion_dry_run_blocks_schema_drift(tmp_path: Path) -> None:
    raw_root = tmp_path / "reports" / "raw"
    _write_fba_reimbursements_raw(
        raw_root,
        "ATVPDKIKX0DER",
        "fba-reimbursements-report-1",
        "approval-date\tunexpected\n2026-05-10\tvalue\n",
    )

    result = FbaReimbursementsIngestionDryRunService(
        raw_reports_root=raw_root,
        output_root=tmp_path / "out",
    ).prepare(marketplace_id="ATVPDKIKX0DER")

    assert result.status == "requires_review"
    assert result.requires_review is True
    assert result.report_result.skipped is True
    assert result.report_result.skip_reason == "schema_validation_requires_review"
    assert result.prepared_row_count == 0
