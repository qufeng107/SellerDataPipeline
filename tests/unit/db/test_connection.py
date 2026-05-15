from __future__ import annotations

import pytest

from seller_data_pipeline.common.exceptions import ConfigurationError
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
