from __future__ import annotations

import json
from pathlib import Path

from seller_data_pipeline.services.report_delivery_service import (
    ReportDeliveryError,
    ReportDeliveryPackService,
)


def test_generate_pack_for_weekly_ads_report(tmp_path: Path) -> None:
    report_json, xlsx_path = _write_report_files(
        tmp_path,
        report_type="weekly_ads_optimization",
        status="ok",
        output_files_path="weekly_ads_optimization_2026-05-11_2026-05-17.xlsx",
    )
    service = ReportDeliveryPackService()

    result = service.generate_pack(
        report_json_path=report_json,
        audience="ads_operator",
        output_root=tmp_path / "delivery",
        dry_run=True,
    )

    assert result.report_type == "weekly_ads_optimization"
    assert result.send_guard.send_allowed is True
    assert result.manifest_path.exists()
    assert result.subject_path.read_text(encoding="utf-8").startswith("[广告优化 Ads Optimization]")
    assert result.body_html_path.exists()
    assert result.body_text_path.exists()
    assert (result.output_dir / "attachments" / xlsx_path.name).exists()
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["delivery_type"] == "report_email_pack"
    assert manifest["email"]["audience"] == "ads_operator"
    assert manifest["send_guard"]["send_allowed"] is True
    assert len(manifest["attachments"]) == 1


def test_include_json_attachment(tmp_path: Path) -> None:
    report_json, _ = _write_report_files(
        tmp_path,
        report_type="monthly_financial_close",
        status="ok",
        output_files_path="monthly_financial_close_2026-04.xlsx",
    )

    result = ReportDeliveryPackService().generate_pack(
        report_json_path=report_json,
        audience="internal",
        output_root=tmp_path / "delivery",
        include_json_attachment=True,
    )

    assert [attachment.kind for attachment in result.attachments] == ["xlsx", "json"]
    assert (result.output_dir / "attachments" / report_json.name).exists()




def test_monthly_delivery_prefers_operating_and_attaches_accounting_workbook(
    tmp_path: Path,
) -> None:
    operating_path = tmp_path / "monthly_operating_report_2026-04.xlsx"
    accounting_path = tmp_path / "accountant_monthly_workbook_2026-04.xlsx"
    legacy_path = tmp_path / "monthly_financial_close_2026-04.xlsx"
    for path in (operating_path, accounting_path, legacy_path):
        path.write_bytes(b"fake xlsx content")
    report_json = tmp_path / "monthly_financial_close_2026-04.json"
    report = _minimal_report(
        report_type="monthly_financial_close",
        status="ok",
        xlsx_path=str(legacy_path),
    )
    report["output_files"] = {
        "xlsx": str(legacy_path),
        "operating_xlsx": str(operating_path),
        "accounting_xlsx": str(accounting_path),
    }
    report_json.write_text(json.dumps(report), encoding="utf-8")

    result = ReportDeliveryPackService().generate_pack(
        report_json_path=report_json,
        audience="shareholders",
        output_root=tmp_path / "delivery",
    )

    assert [attachment.kind for attachment in result.attachments] == [
        "xlsx",
        "accounting_xlsx",
    ]
    assert Path(result.attachments[0].source_path).name == operating_path.name
    assert Path(result.attachments[1].source_path).name == accounting_path.name
    assert (result.output_dir / "attachments" / operating_path.name).exists()
    assert (result.output_dir / "attachments" / accounting_path.name).exists()

def test_partial_report_is_allowed_for_operations_but_blocked_for_shareholders(
    tmp_path: Path,
) -> None:
    report_json, _ = _write_report_files(
        tmp_path,
        report_type="weekly_business_review",
        status="partial",
        output_files_path="weekly_business_review_2026-05-11_2026-05-17.xlsx",
    )
    service = ReportDeliveryPackService()

    operations = service.generate_pack(
        report_json_path=report_json,
        audience="operations",
        output_root=tmp_path / "delivery_ops",
    )
    shareholders = service.generate_pack(
        report_json_path=report_json,
        audience="shareholders",
        output_root=tmp_path / "delivery_shareholders",
    )

    assert operations.send_guard.send_allowed is True
    assert shareholders.send_guard.send_allowed is False
    assert shareholders.send_guard.severity == "blocked"


def test_needs_review_is_blocked_unless_allowed(tmp_path: Path) -> None:
    report_json, _ = _write_report_files(
        tmp_path,
        report_type="monthly_financial_close",
        status="needs_review",
        output_files_path="monthly_financial_close_2026-04.xlsx",
    )
    service = ReportDeliveryPackService()

    blocked = service.generate_pack(
        report_json_path=report_json,
        audience="internal",
        output_root=tmp_path / "delivery_blocked",
    )
    allowed = service.generate_pack(
        report_json_path=report_json,
        audience="internal",
        output_root=tmp_path / "delivery_allowed",
        allow_needs_review=True,
    )

    assert blocked.send_guard.send_allowed is False
    assert allowed.send_guard.send_allowed is True


def test_backslash_xlsx_path_can_resolve_to_report_directory_file(tmp_path: Path) -> None:
    report_json, xlsx_path = _write_report_files(
        tmp_path,
        report_type="weekly_business_review",
        status="ok",
        output_files_path="runtime\\analysis_reports\\weekly_business_review.xlsx",
    )

    result = ReportDeliveryPackService().generate_pack(
        report_json_path=report_json,
        audience="internal",
        output_root=tmp_path / "delivery",
    )

    assert result.attachments[0].source_path == str(xlsx_path)


def test_missing_xlsx_fails_fast(tmp_path: Path) -> None:
    report_json = tmp_path / "report.json"
    report_json.write_text(
        json.dumps(
            {
                "report_type": "weekly_ads_optimization",
                "status": "ok",
                "period": {"week_start": "2026-05-11", "week_end": "2026-05-17"},
                "output_files": {"xlsx": "missing.xlsx"},
            }
        ),
        encoding="utf-8",
    )

    try:
        ReportDeliveryPackService().generate_pack(
            report_json_path=report_json,
            audience="internal",
            output_root=tmp_path / "delivery",
        )
    except ReportDeliveryError as exc:
        assert "XLSX attachment not found" in str(exc)
    else:
        raise AssertionError("Expected missing XLSX to fail")


def _write_report_files(
    tmp_path: Path,
    *,
    report_type: str,
    status: str,
    output_files_path: str,
) -> tuple[Path, Path]:
    xlsx_name = {
        "monthly_financial_close": "monthly_financial_close_2026-04.xlsx",
        "weekly_business_review": "weekly_business_review_2026-05-11_2026-05-17.xlsx",
        "weekly_ads_optimization": "weekly_ads_optimization_2026-05-11_2026-05-17.xlsx",
    }[report_type]
    xlsx_path = tmp_path / xlsx_name
    xlsx_path.write_bytes(b"fake xlsx content")
    report_json = tmp_path / xlsx_name.replace(".xlsx", ".json")
    report = _minimal_report(report_type=report_type, status=status, xlsx_path=output_files_path)
    report_json.write_text(json.dumps(report), encoding="utf-8")
    return report_json, xlsx_path


def _minimal_report(*, report_type: str, status: str, xlsx_path: str) -> dict[str, object]:
    base: dict[str, object] = {
        "report_type": report_type,
        "version": "v1.0",
        "status": status,
        "currency": "USD",
        "marketplace_id": "ATVPDKIKX0DER",
        "profile_id": "3917953989967300",
        "output_files": {"xlsx": xlsx_path},
        "warnings": [{"severity": "info", "warning_code": "scope", "message": "test"}],
    }
    if report_type == "monthly_financial_close":
        base.update(
            {
                "period": {"month": "2026-04"},
                "financial_summary": {
                    "settlement_net_amount": "1853.15",
                    "product_sales_amount": "6241.84",
                    "internal_cogs": "1075.86",
                    "estimated_operating_profit": "777.29",
                    "profit_margin": "0.1245",
                },
            }
        )
    elif report_type == "weekly_business_review":
        base.update(
            {
                "period": {"week_start": "2026-05-11", "week_end": "2026-05-17"},
                "sales_traffic_summary": {"ordered_product_sales": "602.38"},
                "ads_overview": {"summary": {"ads_spend": "105.01"}},
            }
        )
    else:
        base.update(
            {
                "period": {"week_start": "2026-05-11", "week_end": "2026-05-17"},
                "overall_summary": {
                    "ads_spend": "105.01",
                    "ads_sales_7d": "276.00",
                    "acos": "0.3805",
                    "tacos": "0.1743",
                },
                "action_items": [],
                "search_term_action_candidates": [],
            }
        )
    return base
