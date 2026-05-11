from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


@dataclass(frozen=True)
class Settings:
    app_env: str = _env("APP_ENV", "local") or "local"
    log_level: str = _env("LOG_LEVEL", "INFO") or "INFO"

    azure_sql_server: str | None = _env("AZURE_SQL_SERVER")
    azure_sql_database: str | None = _env("AZURE_SQL_DATABASE")
    azure_sql_username: str | None = _env("AZURE_SQL_USERNAME")
    azure_sql_password: str | None = _env("AZURE_SQL_PASSWORD")
    azure_sql_driver: str = _env("AZURE_SQL_DRIVER", "ODBC Driver 18 for SQL Server") or "ODBC Driver 18 for SQL Server"

    amazon_region: str = _env("AMAZON_REGION", "NA") or "NA"
    amazon_marketplace_id: str | None = _env("AMAZON_MARKETPLACE_ID")
    amazon_lwa_client_id: str | None = _env("AMAZON_LWA_CLIENT_ID")
    amazon_lwa_client_secret: str | None = _env("AMAZON_LWA_CLIENT_SECRET")
    amazon_sp_api_refresh_token: str | None = _env("AMAZON_SP_API_REFRESH_TOKEN")
    amazon_ads_refresh_token: str | None = _env("AMAZON_ADS_REFRESH_TOKEN")

    report_receiver_email: str | None = _env("REPORT_RECEIVER_EMAIL")


def get_settings() -> Settings:
    return Settings()
