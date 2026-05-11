from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import pyodbc

from seller_data_pipeline.config.settings import Settings, get_settings
from seller_data_pipeline.common.exceptions import ConfigurationError


def build_connection_string(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    required = [
        settings.azure_sql_server,
        settings.azure_sql_database,
        settings.azure_sql_username,
        settings.azure_sql_password,
    ]
    if any(value in (None, "") for value in required):
        raise ConfigurationError("Azure SQL settings are incomplete")

    return (
        f"DRIVER={{{settings.azure_sql_driver}}};"
        f"SERVER={settings.azure_sql_server};"
        f"DATABASE={settings.azure_sql_database};"
        f"UID={settings.azure_sql_username};"
        f"PWD={settings.azure_sql_password};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )


@contextmanager
def get_connection(settings: Settings | None = None) -> Iterator[pyodbc.Connection]:
    conn = pyodbc.connect(build_connection_string(settings))
    try:
        yield conn
    finally:
        conn.close()
