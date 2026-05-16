from __future__ import annotations

import importlib.util
from datetime import datetime
from decimal import Decimal
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


check_database_status = _load_script_module(
    "scripts/check_database_status.py",
    "check_database_status_for_test",
)


def test_build_table_count_query_uses_safe_identifiers() -> None:
    sql = check_database_status.build_table_count_query(
        ["amazon_ads_sp_campaign_daily", "amazon_sync_run_log"]
    )

    assert "FROM dbo.[amazon_ads_sp_campaign_daily]" in sql
    assert "UNION ALL" in sql
    assert sql.endswith(";")


def test_build_table_count_query_rejects_unsafe_table_name() -> None:
    with pytest.raises(ValueError, match="Unsafe table name"):
        check_database_status.build_table_count_query(["amazon_sync_run_log;DROP TABLE x"])


def test_json_ready_serialises_datetime_and_decimal() -> None:
    assert check_database_status.json_ready(datetime(2026, 5, 16, 21, 30)) == "2026-05-16T21:30:00"
    assert check_database_status.json_ready(Decimal("12.3400")) == "12.3400"
