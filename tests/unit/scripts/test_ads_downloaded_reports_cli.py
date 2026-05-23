from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import ModuleType

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load_script_module(relative_path: str, module_name: str) -> ModuleType:
    script_path = PROJECT_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


analyze_ads_downloaded_reports = _load_script_module(
    "scripts/analyze_ads_downloaded_reports.py",
    "analyze_ads_downloaded_reports_for_test",
)


def test_build_ads_sample_output_path_sanitizes_report_type() -> None:
    path = analyze_ads_downloaded_reports.build_ads_sample_output_path(
        Path("docs/data_access/sample_notes"),
        "sp:Campaigns",
    )

    assert path == Path("docs/data_access/sample_notes/ADS_sp_Campaigns.md")


def test_find_latest_ads_raw_file_returns_newest(tmp_path: Path) -> None:
    root = tmp_path / "reports"
    old_file = root / "amazon_ads" / "123" / "spCampaigns" / "2026-05-14" / "old.json"
    new_file = root / "amazon_ads" / "123" / "spCampaigns" / "2026-05-15" / "new.json"
    old_file.parent.mkdir(parents=True)
    new_file.parent.mkdir(parents=True)
    old_file.write_text("[]", encoding="utf-8")
    new_file.write_text("[]", encoding="utf-8")
    old_time = 1_700_000_000
    new_time = 1_800_000_000
    os.utime(old_file, (old_time, old_time))
    os.utime(new_file, (new_time, new_time))

    assert (
        analyze_ads_downloaded_reports.find_latest_ads_raw_file(
            raw_reports_root=str(root),
            profile_id="123",
            report_type_id="spCampaigns",
        )
        == new_file
    )


def test_find_latest_ads_raw_file_returns_none_when_missing(tmp_path: Path) -> None:
    assert (
        analyze_ads_downloaded_reports.find_latest_ads_raw_file(
            raw_reports_root=str(tmp_path),
            profile_id="123",
            report_type_id="spCampaigns",
        )
        is None
    )
