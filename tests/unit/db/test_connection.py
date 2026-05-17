from __future__ import annotations

import pytest

from seller_data_pipeline.common.exceptions import AzureSqlConnectionError, ConfigurationError
from seller_data_pipeline.config.settings import Settings
from seller_data_pipeline.db.connection import build_connection_string


def test_build_sql_password_connection_string() -> None:
    settings = Settings(
        azure_sql_server="tcp:test.database.windows.net,1433",
        azure_sql_database="SellerDataPipeline",
        azure_sql_username="sql_user",
        azure_sql_password="secret",
        azure_sql_driver="ODBC Driver 18 for SQL Server",
        azure_sql_auth_mode="sql_password",
        azure_sql_encrypt="yes",
        azure_sql_trust_server_certificate="no",
        azure_sql_connection_timeout=30,
    )

    connection_string = build_connection_string(settings)

    assert "DRIVER={ODBC Driver 18 for SQL Server};" in connection_string
    assert "SERVER=tcp:test.database.windows.net,1433;" in connection_string
    assert "DATABASE=SellerDataPipeline;" in connection_string
    assert "UID=sql_user;" in connection_string
    assert "PWD=secret;" in connection_string
    assert "Encrypt=yes;" in connection_string
    assert "TrustServerCertificate=no;" in connection_string
    assert "Connection Timeout=30;" in connection_string


def test_missing_sql_password_setting_raises_configuration_error() -> None:
    settings = Settings(
        azure_sql_server="tcp:test.database.windows.net,1433",
        azure_sql_database="SellerDataPipeline",
        azure_sql_username="sql_user",
        azure_sql_password=None,
        azure_sql_auth_mode="sql_password",
    )

    with pytest.raises(ConfigurationError, match="AZURE_SQL_PASSWORD"):
        build_connection_string(settings)


def test_build_managed_identity_connection_string_without_password() -> None:
    settings = Settings(
        azure_sql_server="tcp:test.database.windows.net,1433",
        azure_sql_database="SellerDataPipeline",
        azure_sql_username=None,
        azure_sql_password=None,
        azure_sql_auth_mode="entra_managed_identity",
        azure_sql_managed_identity_client_id="client-id-123",
    )

    connection_string = build_connection_string(settings)

    assert "Authentication=ActiveDirectoryMsi;" in connection_string
    assert "UID=client-id-123;" in connection_string
    assert "PWD=" not in connection_string


def test_unsupported_auth_mode_raises_configuration_error() -> None:
    settings = Settings(
        azure_sql_server="tcp:test.database.windows.net,1433",
        azure_sql_database="SellerDataPipeline",
        azure_sql_auth_mode="unknown",
    )

    with pytest.raises(ConfigurationError, match="Unsupported AZURE_SQL_AUTH_MODE"):
        build_connection_string(settings)


class FakeOdbcError(Exception):
    pass


class FakeWarmupCursor:
    def __init__(self) -> None:
        self.executed: list[str] = []
        self.closed = False

    def execute(self, sql: str) -> None:
        self.executed.append(sql)

    def fetchone(self) -> list[int]:
        return [1]

    def close(self) -> None:
        self.closed = True


class FakeOdbcConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeWarmupCursor()
        self.closed = False

    def cursor(self) -> FakeWarmupCursor:
        return self.cursor_instance

    def close(self) -> None:
        self.closed = True


class FakePyodbcModule:
    Error = FakeOdbcError

    def __init__(self, failures_before_success: int = 0, error_text: str = "08001") -> None:
        self.failures_before_success = failures_before_success
        self.error_text = error_text
        self.calls = 0
        self.connections: list[FakeOdbcConnection] = []

    def connect(self, connection_string: str, autocommit: bool) -> FakeOdbcConnection:
        self.calls += 1
        if self.calls <= self.failures_before_success:
            raise FakeOdbcError(self.error_text, "Login timeout expired")
        connection = FakeOdbcConnection()
        self.connections.append(connection)
        return connection


def _complete_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "azure_sql_server": "tcp:test.database.windows.net,1433",
        "azure_sql_database": "SellerDataPipeline",
        "azure_sql_username": "sql_user",
        "azure_sql_password": "secret",
        "azure_sql_driver": "ODBC Driver 18 for SQL Server",
        "azure_sql_auth_mode": "sql_password",
        "azure_sql_connection_timeout": 30,
        "azure_sql_connect_max_attempts": 2,
        "azure_sql_connect_retry_delay_seconds": 0,
        "azure_sql_connect_retry_backoff": 1,
    }
    base.update(overrides)
    return Settings(**base)


def test_get_connection_retries_retryable_login_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    from seller_data_pipeline.db import connection as connection_module

    fake_pyodbc = FakePyodbcModule(failures_before_success=1, error_text="08001")
    monkeypatch.setattr(connection_module, "_import_pyodbc", lambda: fake_pyodbc)

    with connection_module.get_connection(settings=_complete_settings()) as conn:
        assert isinstance(conn, FakeOdbcConnection)
        assert conn.cursor_instance.executed == ["SELECT 1"]

    assert fake_pyodbc.calls == 2
    assert fake_pyodbc.connections[0].closed is True


def test_get_connection_does_not_retry_non_retryable_login_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from seller_data_pipeline.db import connection as connection_module

    fake_pyodbc = FakePyodbcModule(failures_before_success=2, error_text="28000")
    monkeypatch.setattr(connection_module, "_import_pyodbc", lambda: fake_pyodbc)

    with pytest.raises(AzureSqlConnectionError, match="login/authentication was rejected"):
        with connection_module.get_connection(settings=_complete_settings()):
            pass

    assert fake_pyodbc.calls == 1


def test_firewall_error_is_not_retried_and_message_contains_blocked_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from seller_data_pipeline.db import connection as connection_module

    fake_pyodbc = FakePyodbcModule(
        failures_before_success=2,
        error_text=(
            "42000 Cannot open server requested by the login. "
            "Client with IP address '185.69.144.165' is not allowed to access the server. "
            "Create a firewall rule. (40615)"
        ),
    )
    monkeypatch.setattr(connection_module, "_import_pyodbc", lambda: fake_pyodbc)

    with pytest.raises(AzureSqlConnectionError) as exc_info:
        with connection_module.get_connection(settings=_complete_settings()):
            pass

    assert fake_pyodbc.calls == 1
    message = str(exc_info.value)
    assert "firewall" in message
    assert "185.69.144.165" in message
    assert "not an auto-pause warm-up failure" in message


def test_retryable_error_after_max_attempts_has_actionable_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from seller_data_pipeline.db import connection as connection_module

    fake_pyodbc = FakePyodbcModule(failures_before_success=3, error_text="08001")
    monkeypatch.setattr(connection_module, "_import_pyodbc", lambda: fake_pyodbc)

    with pytest.raises(AzureSqlConnectionError) as exc_info:
        with connection_module.get_connection(settings=_complete_settings()):
            pass

    assert fake_pyodbc.calls == 2
    message = str(exc_info.value)
    assert "2/2 attempts" in message
    assert "serverless database is resuming" in message
