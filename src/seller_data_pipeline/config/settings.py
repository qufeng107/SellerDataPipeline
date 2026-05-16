from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

DEFAULT_AZURE_SQL_DRIVER = "ODBC Driver 18 for SQL Server"
DEFAULT_AMAZON_SP_API_ENDPOINTS = {
    "NA": "https://sellingpartnerapi-na.amazon.com",
    "EU": "https://sellingpartnerapi-eu.amazon.com",
    "FE": "https://sellingpartnerapi-fe.amazon.com",
}
DEFAULT_AMAZON_ADS_API_ENDPOINTS = {
    "NA": "https://advertising-api.amazon.com",
    "EU": "https://advertising-api-eu.amazon.com",
    "FE": "https://advertising-api-fe.amazon.com",
}
DEFAULT_LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
DEFAULT_USER_AGENT = "SellerDataPipeline/0.1.0 (Language=Python/3.11)"
DEFAULT_LOCAL_SAMPLING_ROOT = "runtime/sampling"
DEFAULT_RAW_REPORTS_ROOT = "reports/raw"
DEFAULT_AZURE_SQL_AUTH_MODE = "sql_password"
DEFAULT_AZURE_SQL_ENCRYPT = "yes"
DEFAULT_AZURE_SQL_TRUST_SERVER_CERTIFICATE = "no"
DEFAULT_AZURE_SQL_CONNECTION_TIMEOUT = 30
DEFAULT_AZURE_SQL_CONNECT_MAX_ATTEMPTS = 4
DEFAULT_AZURE_SQL_CONNECT_RETRY_DELAY_SECONDS = 5.0
DEFAULT_AZURE_SQL_CONNECT_RETRY_BACKOFF = 1.8


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _default_sp_api_endpoint(region: str) -> str:
    return DEFAULT_AMAZON_SP_API_ENDPOINTS.get(
        region.upper(),
        DEFAULT_AMAZON_SP_API_ENDPOINTS["NA"],
    )


def _default_ads_api_endpoint(region: str) -> str:
    return DEFAULT_AMAZON_ADS_API_ENDPOINTS.get(
        region.upper(),
        DEFAULT_AMAZON_ADS_API_ENDPOINTS["NA"],
    )


def _default_ads_region() -> str:
    return _env("AMAZON_ADS_REGION", _env("AMAZON_REGION", "NA")) or "NA"


@dataclass(frozen=True)
class Settings:
    app_env: str = _env("APP_ENV", "local") or "local"
    log_level: str = _env("LOG_LEVEL", "INFO") or "INFO"

    azure_sql_server: str | None = _env("AZURE_SQL_SERVER")
    azure_sql_database: str | None = _env("AZURE_SQL_DATABASE")
    azure_sql_username: str | None = _env("AZURE_SQL_USERNAME")
    azure_sql_password: str | None = _env("AZURE_SQL_PASSWORD")
    azure_sql_driver: str = _env("AZURE_SQL_DRIVER", DEFAULT_AZURE_SQL_DRIVER) or (
        DEFAULT_AZURE_SQL_DRIVER
    )
    azure_sql_auth_mode: str = _env("AZURE_SQL_AUTH_MODE", DEFAULT_AZURE_SQL_AUTH_MODE) or (
        DEFAULT_AZURE_SQL_AUTH_MODE
    )
    azure_sql_encrypt: str = _env("AZURE_SQL_ENCRYPT", DEFAULT_AZURE_SQL_ENCRYPT) or (
        DEFAULT_AZURE_SQL_ENCRYPT
    )
    azure_sql_trust_server_certificate: str = _env(
        "AZURE_SQL_TRUST_SERVER_CERTIFICATE",
        DEFAULT_AZURE_SQL_TRUST_SERVER_CERTIFICATE,
    ) or DEFAULT_AZURE_SQL_TRUST_SERVER_CERTIFICATE
    azure_sql_connection_timeout: int = _env_int(
        "AZURE_SQL_CONNECTION_TIMEOUT",
        DEFAULT_AZURE_SQL_CONNECTION_TIMEOUT,
    )
    azure_sql_connect_max_attempts: int = _env_int(
        "AZURE_SQL_CONNECT_MAX_ATTEMPTS",
        DEFAULT_AZURE_SQL_CONNECT_MAX_ATTEMPTS,
    )
    azure_sql_connect_retry_delay_seconds: float = _env_float(
        "AZURE_SQL_CONNECT_RETRY_DELAY_SECONDS",
        DEFAULT_AZURE_SQL_CONNECT_RETRY_DELAY_SECONDS,
    )
    azure_sql_connect_retry_backoff: float = _env_float(
        "AZURE_SQL_CONNECT_RETRY_BACKOFF",
        DEFAULT_AZURE_SQL_CONNECT_RETRY_BACKOFF,
    )
    azure_sql_managed_identity_client_id: str | None = _env(
        "AZURE_SQL_MANAGED_IDENTITY_CLIENT_ID"
    )

    amazon_region: str = _env("AMAZON_REGION", "NA") or "NA"
    amazon_marketplace_id: str | None = _env("AMAZON_MARKETPLACE_ID")
    amazon_lwa_client_id: str | None = _env("AMAZON_LWA_CLIENT_ID")
    amazon_lwa_client_secret: str | None = _env("AMAZON_LWA_CLIENT_SECRET")
    amazon_sp_api_refresh_token: str | None = _env("AMAZON_SP_API_REFRESH_TOKEN")
    amazon_sp_api_endpoint: str = (
        _env(
            "AMAZON_SP_API_ENDPOINT",
            _default_sp_api_endpoint(_env("AMAZON_REGION", "NA") or "NA"),
        )
        or DEFAULT_AMAZON_SP_API_ENDPOINTS["NA"]
    )
    amazon_lwa_token_url: str = _env("AMAZON_LWA_TOKEN_URL", DEFAULT_LWA_TOKEN_URL) or (
        DEFAULT_LWA_TOKEN_URL
    )
    amazon_sp_api_user_agent: str = _env("AMAZON_SP_API_USER_AGENT", DEFAULT_USER_AGENT) or (
        DEFAULT_USER_AGENT
    )
    amazon_ads_region: str = _default_ads_region()
    amazon_ads_client_id: str | None = _env("AMAZON_ADS_CLIENT_ID", _env("AMAZON_LWA_CLIENT_ID"))
    amazon_ads_client_secret: str | None = _env(
        "AMAZON_ADS_CLIENT_SECRET",
        _env("AMAZON_LWA_CLIENT_SECRET"),
    )
    amazon_ads_refresh_token: str | None = _env("AMAZON_ADS_REFRESH_TOKEN")
    amazon_ads_profile_id: str | None = _env("AMAZON_ADS_PROFILE_ID")
    amazon_ads_api_endpoint: str = (
        _env(
            "AMAZON_ADS_API_ENDPOINT",
            _default_ads_api_endpoint(_default_ads_region()),
        )
        or DEFAULT_AMAZON_ADS_API_ENDPOINTS["NA"]
    )
    amazon_ads_user_agent: str = _env("AMAZON_ADS_USER_AGENT", DEFAULT_USER_AGENT) or (
        DEFAULT_USER_AGENT
    )

    local_sampling_root: str = _env("LOCAL_SAMPLING_ROOT", DEFAULT_LOCAL_SAMPLING_ROOT) or (
        DEFAULT_LOCAL_SAMPLING_ROOT
    )
    raw_reports_root: str = _env("RAW_REPORTS_ROOT", DEFAULT_RAW_REPORTS_ROOT) or (
        DEFAULT_RAW_REPORTS_ROOT
    )

    report_receiver_email: str | None = _env("REPORT_RECEIVER_EMAIL")


def get_settings() -> Settings:
    return Settings()
