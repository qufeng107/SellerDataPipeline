from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from seller_data_pipeline.common.exceptions import ConfigurationError
from seller_data_pipeline.config.settings import Settings, get_settings

SQL_PASSWORD_AUTH_MODE = "sql_password"
ENTRA_MANAGED_IDENTITY_AUTH_MODE = "entra_managed_identity"
SUPPORTED_AUTH_MODES = {SQL_PASSWORD_AUTH_MODE, ENTRA_MANAGED_IDENTITY_AUTH_MODE}


def _normalise_auth_mode(value: str | None) -> str:
    auth_mode = (value or SQL_PASSWORD_AUTH_MODE).strip().lower().replace("-", "_")
    if auth_mode not in SUPPORTED_AUTH_MODES:
        supported = ", ".join(sorted(SUPPORTED_AUTH_MODES))
        raise ConfigurationError(
            f"Unsupported AZURE_SQL_AUTH_MODE={value!r}. Supported values: {supported}."
        )
    return auth_mode


def _require(value: str | int | None, env_name: str) -> str:
    if value in (None, ""):
        raise ConfigurationError(f"Azure SQL setting {env_name} is required")
    return str(value)


def _append_common_options(parts: list[str], settings: Settings) -> None:
    parts.extend(
        [
            f"Encrypt={settings.azure_sql_encrypt}",
            f"TrustServerCertificate={settings.azure_sql_trust_server_certificate}",
            f"Connection Timeout={settings.azure_sql_connection_timeout}",
        ]
    )


def build_connection_string(settings: Settings | None = None) -> str:
    """Build an Azure SQL pyodbc connection string from project settings.

    The default mode is SQL username/password because it is the simplest path for
    local migration execution. Managed identity is intentionally supported as a
    later cloud-job mode, so the same DB adapter can be reused by Azure-hosted
    jobs without storing a long-lived database password.
    """

    settings = settings or get_settings()
    auth_mode = _normalise_auth_mode(settings.azure_sql_auth_mode)
    parts = [
        f"DRIVER={{{_require(settings.azure_sql_driver, 'AZURE_SQL_DRIVER')}}}",
        f"SERVER={_require(settings.azure_sql_server, 'AZURE_SQL_SERVER')}",
        f"DATABASE={_require(settings.azure_sql_database, 'AZURE_SQL_DATABASE')}",
    ]

    if auth_mode == SQL_PASSWORD_AUTH_MODE:
        parts.extend(
            [
                f"UID={_require(settings.azure_sql_username, 'AZURE_SQL_USERNAME')}",
                f"PWD={_require(settings.azure_sql_password, 'AZURE_SQL_PASSWORD')}",
            ]
        )
    elif auth_mode == ENTRA_MANAGED_IDENTITY_AUTH_MODE:
        parts.append("Authentication=ActiveDirectoryMsi")
        if settings.azure_sql_managed_identity_client_id:
            parts.append(f"UID={settings.azure_sql_managed_identity_client_id}")

    _append_common_options(parts, settings)
    return ";".join(parts) + ";"


def _import_pyodbc() -> Any:
    try:
        import pyodbc  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise ConfigurationError(
            "pyodbc is not installed. Install project requirements and the Microsoft ODBC "
            "Driver for SQL Server before connecting to Azure SQL."
        ) from exc
    return pyodbc


@contextmanager
def get_connection(
    settings: Settings | None = None,
    *,
    autocommit: bool = False,
) -> Iterator[Any]:
    """Open an Azure SQL connection.

    pyodbc is imported lazily so unit tests and pure parser workflows can run on
    machines that do not yet have the native ODBC driver installed.
    """

    pyodbc = _import_pyodbc()
    conn = pyodbc.connect(build_connection_string(settings), autocommit=autocommit)
    try:
        yield conn
    finally:
        conn.close()


def run_connection_diagnostics(settings: Settings | None = None) -> dict[str, Any]:
    """Return a small, non-sensitive Azure SQL connectivity diagnostic payload."""

    with get_connection(settings=settings) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    DB_NAME() AS database_name,
                    SUSER_SNAME() AS login_name,
                    CAST(SERVERPROPERTY('ServerName') AS nvarchar(256)) AS server_name,
                    CAST(SERVERPROPERTY('Edition') AS nvarchar(256)) AS edition
                """
            )
            row = cursor.fetchone()
            cursor.execute("SELECT COUNT(*) FROM sys.tables WHERE is_ms_shipped = 0")
            user_table_count = int(cursor.fetchone()[0])
        finally:
            cursor.close()

    return {
        "database_name": row[0],
        "login_name": row[1],
        "server_name": row[2],
        "edition": row[3],
        "user_table_count": user_table_count,
    }


def list_user_tables(settings: Settings | None = None) -> list[dict[str, str]]:
    """List user-created tables in the current Azure SQL database."""

    with get_connection(settings=settings) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT s.name AS schema_name, t.name AS table_name
                FROM sys.tables AS t
                INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
                WHERE t.is_ms_shipped = 0
                ORDER BY s.name, t.name
                """
            )
            rows = cursor.fetchall()
        finally:
            cursor.close()

    return [{"schema_name": row[0], "table_name": row[1]} for row in rows]
