from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from seller_data_pipeline.common.exceptions import AzureSqlConnectionError, ConfigurationError
from seller_data_pipeline.config.settings import Settings, get_settings

SQL_PASSWORD_AUTH_MODE = "sql_password"
ENTRA_MANAGED_IDENTITY_AUTH_MODE = "entra_managed_identity"
SUPPORTED_AUTH_MODES = {SQL_PASSWORD_AUTH_MODE, ENTRA_MANAGED_IDENTITY_AUTH_MODE}
_RETRYABLE_CONNECTION_MARKERS = (
    "08001",  # SQLDriverConnect/login timeout, common during Azure SQL serverless resume.
    "08S01",  # Communication link failure.
    "HYT00",  # Timeout expired.
    "HYT01",  # Connection timeout expired.
    "40613",  # Database is not currently available.
    "40197",  # Azure SQL transient service error.
    "40501",  # Azure SQL service busy/throttling.
)
_FIREWALL_DENIED_MARKERS = (
    "40615",
    "not allowed to access the server",
    "create a firewall rule",
)
_LOGIN_AUTH_FAILURE_MARKERS = (
    "18456",
    "Login failed",
    "28000",
)
_WARMUP_SQL = "SELECT 1"
logger = logging.getLogger(__name__)


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


def _safe_max_attempts(settings: Settings) -> int:
    return max(1, int(settings.azure_sql_connect_max_attempts))


def _safe_retry_delay(settings: Settings) -> float:
    return max(0.0, float(settings.azure_sql_connect_retry_delay_seconds))


def _safe_retry_backoff(settings: Settings) -> float:
    return max(1.0, float(settings.azure_sql_connect_retry_backoff))


def is_retryable_connection_error(exc: BaseException) -> bool:
    """Return True for transient Azure SQL connection/resume failures.

    Keep this intentionally narrow. Authentication errors, SQL syntax errors, and
    business query failures must fail fast rather than being retried blindly.
    """

    text = " ".join(str(arg) for arg in getattr(exc, "args", ())) or str(exc)
    return any(marker in text for marker in _RETRYABLE_CONNECTION_MARKERS)


def _odbc_error_text(exc: BaseException) -> str:
    return " ".join(str(arg) for arg in getattr(exc, "args", ())) or str(exc)


def _contains_any_marker(text: str, markers: tuple[str, ...]) -> bool:
    lower_text = text.lower()
    return any(marker.lower() in lower_text for marker in markers)


def is_azure_sql_firewall_error(exc: BaseException) -> bool:
    """Return True when Azure SQL rejected the client IP before login."""

    return _contains_any_marker(_odbc_error_text(exc), _FIREWALL_DENIED_MARKERS)


def is_login_authentication_error(exc: BaseException) -> bool:
    """Return True for obvious SQL login/authentication failures."""

    return _contains_any_marker(_odbc_error_text(exc), _LOGIN_AUTH_FAILURE_MARKERS)


def extract_azure_sql_blocked_client_ip(exc: BaseException) -> str | None:
    """Extract the blocked client IP from Azure SQL firewall error text, when present."""

    import re

    text = _odbc_error_text(exc)
    match = re.search(r"Client with IP address '([^']+)'", text)
    if match:
        return match.group(1)
    return None


def build_azure_sql_connection_error_message(
    exc: BaseException,
    *,
    attempt: int,
    max_attempts: int,
) -> str:
    """Build an actionable connection error message for CLI users and automation logs."""

    if is_azure_sql_firewall_error(exc):
        client_ip = extract_azure_sql_blocked_client_ip(exc)
        ip_suffix = f" Current client IP: {client_ip}." if client_ip else ""
        return (
            "Azure SQL connection failed because the current client IP is not allowed by "
            "the Azure SQL Server firewall. This is not an auto-pause warm-up failure and "
            f"should not be fixed by retrying.{ip_suffix} Add this IP to the Azure SQL "
            "firewall allowlist in Azure Portal, or run sp_set_firewall_rule on the master "
            "database, then wait a few minutes and retry."
        )

    if is_login_authentication_error(exc):
        return (
            "Azure SQL connection failed because SQL login/authentication was rejected. "
            "Check AZURE_SQL_USERNAME, AZURE_SQL_PASSWORD, AZURE_SQL_AUTH_MODE, and whether "
            "the login has access to the configured database."
        )

    if is_retryable_connection_error(exc):
        return (
            "Azure SQL connection warm-up failed after "
            f"{attempt}/{max_attempts} attempts with a retryable ODBC error. This can happen "
            "while an Azure SQL serverless database is resuming from idle. Retry later or "
            "increase AZURE_SQL_CONNECT_MAX_ATTEMPTS / AZURE_SQL_CONNECT_RETRY_DELAY_SECONDS "
            "if the database needs longer to resume. Last ODBC error: "
            f"{exc}"
        )

    return (
        "Azure SQL connection failed with a non-retryable ODBC error. Check Azure SQL "
        "server/database settings, network access, firewall, credentials, and ODBC Driver 18 "
        f"installation. ODBC error: {exc}"
    )


def _raise_azure_sql_connection_error(
    exc: BaseException,
    *,
    attempt: int,
    max_attempts: int,
) -> None:
    raise AzureSqlConnectionError(
        build_azure_sql_connection_error_message(
            exc,
            attempt=attempt,
            max_attempts=max_attempts,
        )
    ) from exc


def _warm_up_connection(connection: Any) -> None:
    """Run a tiny query before yielding a connection to business code."""

    cursor = connection.cursor()
    try:
        cursor.execute(_WARMUP_SQL)
        cursor.fetchone()
    finally:
        cursor.close()


def _close_quietly(connection: Any | None) -> None:
    if connection is None:
        return
    try:
        connection.close()
    except Exception:  # pragma: no cover - defensive cleanup path
        logger.debug("Failed to close Azure SQL connection after failed warm-up", exc_info=True)


def _connect_with_retry(pyodbc: Any, settings: Settings, *, autocommit: bool) -> Any:
    max_attempts = _safe_max_attempts(settings)
    retry_delay = _safe_retry_delay(settings)
    retry_backoff = _safe_retry_backoff(settings)
    connection_string = build_connection_string(settings)
    last_exception: BaseException | None = None

    for attempt in range(1, max_attempts + 1):
        connection = None
        try:
            connection = pyodbc.connect(connection_string, autocommit=autocommit)
            _warm_up_connection(connection)
            if attempt > 1:
                logger.info(
                    "Azure SQL connection warm-up succeeded after %s/%s attempts.",
                    attempt,
                    max_attempts,
                )
            return connection
        except pyodbc.Error as exc:  # type: ignore[attr-defined]
            _close_quietly(connection)
            last_exception = exc
            if not is_retryable_connection_error(exc) or attempt >= max_attempts:
                _raise_azure_sql_connection_error(
                    exc,
                    attempt=attempt,
                    max_attempts=max_attempts,
                )
            sleep_seconds = retry_delay * (retry_backoff ** (attempt - 1))
            logger.warning(
                "Azure SQL connection warm-up attempt %s/%s failed with a retryable "
                "ODBC error; retrying in %.1f seconds. error=%s",
                attempt,
                max_attempts,
                sleep_seconds,
                exc,
            )
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

    if last_exception is not None:  # pragma: no cover - defensive branch
        raise last_exception
    raise RuntimeError("Azure SQL connection retry loop exited unexpectedly")


@contextmanager
def get_connection(
    settings: Settings | None = None,
    *,
    autocommit: bool = False,
) -> Iterator[Any]:
    """Open an Azure SQL connection and verify it before business SQL runs.

    Azure SQL serverless databases can be slow to accept the first login after an
    idle period. The project therefore retries only the connection/warm-up phase
    for known transient ODBC errors, then yields a verified connection to the
    caller. Business SQL itself is not retried here; ingestion idempotency and
    migration transaction rules remain the caller's responsibility.
    """

    settings = settings or get_settings()
    pyodbc = _import_pyodbc()
    conn = _connect_with_retry(pyodbc, settings, autocommit=autocommit)
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
