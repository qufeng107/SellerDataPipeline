from pathlib import Path

from seller_data_pipeline.ingestion.inventory_ledger_ingestion_dry_run import (
    InventoryLedgerIngestionDryRunService,
)


def test_inventory_ledger_dry_run_uses_latest_valid_raw_files(tmp_path: Path) -> None:
    service = InventoryLedgerIngestionDryRunService(
        raw_reports_root="reports/raw",
        output_root=tmp_path,
    )
    result = service.prepare(marketplace_id="ATVPDKIKX0DER")
    assert result.status == "success"
    assert result.requires_review is False
    assert result.prepared_row_count == 357
    assert result.preview_file_count == 2
    table_counts = {}
    for report_result in result.report_results:
        table_counts.update(report_result.table_row_counts)
    assert table_counts["amazon_inventory_ledger_summary_daily"] == 150
    assert table_counts["amazon_inventory_ledger_detail"] == 207
