from __future__ import annotations

import importlib.util
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


inspect_ingestion_preview = _load_script_module(
    "scripts/inspect_ingestion_preview.py",
    "inspect_ingestion_preview_for_test",
)


def test_redact_sensitive_fields_keeps_metrics() -> None:
    row = {
        "campaign_name": "PD2026_护照包_手动精准",
        "search_term": "passport holder",
        "clicks": 3,
        "cost": "1.23",
    }

    redacted = inspect_ingestion_preview.redact_sensitive_fields(row)

    assert redacted["campaign_name"] == "<redacted>"
    assert redacted["search_term"] == "<redacted>"
    assert redacted["clicks"] == 3
    assert redacted["cost"] == "1.23"
