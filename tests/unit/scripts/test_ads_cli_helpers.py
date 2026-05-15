from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import ModuleType

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load_script_module(relative_path: str, module_name: str) -> ModuleType:
    script_path = PROJECT_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


analyze_ads_raw_report = _load_script_module(
    "scripts/analyze_ads_raw_report.py",
    "analyze_ads_raw_report_for_test",
)
test_ads_api_connection = _load_script_module(
    "scripts/test_ads_api_connection.py",
    "test_ads_api_connection_for_test",
)


def test_select_recommended_profile_prefers_selected_when_found() -> None:
    payload = {
        "selected_profile_id": "3917953989967300",
        "selected_profile_found": True,
        "profiles": [
            {
                "profileId": "909721457096469",
                "countryCode": "BR",
                "currencyCode": "BRL",
                "accountInfo": {"type": "seller", "validPaymentMethod": False},
            }
        ],
    }

    assert test_ads_api_connection._select_recommended_profile(payload) == "3917953989967300"


def test_select_recommended_profile_prefers_us_seller_with_valid_payment() -> None:
    payload = {
        "selected_profile_id": None,
        "selected_profile_found": False,
        "profiles": [
            {
                "profileId": "909721457096469",
                "countryCode": "BR",
                "currencyCode": "BRL",
                "accountInfo": {"type": "seller", "validPaymentMethod": False},
            },
            {
                "profileId": "37899657223314",
                "countryCode": "CA",
                "currencyCode": "CAD",
                "accountInfo": {"type": "seller", "validPaymentMethod": True},
            },
            {
                "profileId": "3917953989967300",
                "countryCode": "US",
                "currencyCode": "USD",
                "accountInfo": {"type": "seller", "validPaymentMethod": True},
            },
        ],
    }

    assert test_ads_api_connection._select_recommended_profile(payload) == "3917953989967300"


def test_resolve_ads_raw_file_latest(tmp_path: Path) -> None:
    root = tmp_path / "reports" / "raw"
    old_file = root / "amazon_ads" / "3917953989967300" / "spCampaigns" / "2026-05-14" / "old.json"
    new_file = root / "amazon_ads" / "3917953989967300" / "spCampaigns" / "2026-05-15" / "new.json"
    old_file.parent.mkdir(parents=True)
    new_file.parent.mkdir(parents=True)
    old_file.write_text("[]", encoding="utf-8")
    new_file.write_text("[]", encoding="utf-8")
    os.utime(old_file, (1_700_000_000, 1_700_000_000))
    os.utime(new_file, (1_700_000_100, 1_700_000_100))

    assert analyze_ads_raw_report._resolve_raw_file_path(
        raw_file_arg=None,
        latest=True,
        raw_reports_root=str(root),
        profile_id="3917953989967300",
        report_type_id="spCampaigns",
    ) == new_file


def test_resolve_ads_raw_file_requires_explicit_mode(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="Either --raw-file or --latest is required"):
        analyze_ads_raw_report._resolve_raw_file_path(
            raw_file_arg=None,
            latest=False,
            raw_reports_root=str(tmp_path),
            profile_id="3917953989967300",
            report_type_id="spCampaigns",
        )
