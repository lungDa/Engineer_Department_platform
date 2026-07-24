import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parents[1]

if load_dotenv:
    load_dotenv(BASE_DIR / ".env")


def _get_secret(name: str, default: str = "") -> str:
    """Read Render/local env first, then common Streamlit secret layouts."""
    env_value = os.getenv(name)
    if env_value is not None and str(env_value).strip():
        return str(env_value).strip()

    try:
        import streamlit as st

        aliases = (name, name.lower())
        for key in aliases:
            value = st.secrets.get(key, default)
            if value is not None and str(value).strip():
                return str(value).strip()

        # Accept both [line] and [LINE], with upper- or lower-case keys.
        for section_name in ("line", "LINE"):
            line_secrets = st.secrets.get(section_name, {})
            for key in aliases:
                nested_value = line_secrets.get(key, default)
                if nested_value is not None and str(nested_value).strip():
                    return str(nested_value).strip()
        return default
    except Exception:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Engineer Department Platform")
    app_version: str = os.getenv("APP_VERSION", "V5.6.0 Microsoft 365 Notifications Foundation")
    environment: str = os.getenv("ENVIRONMENT", "development")

    streamlit_base_url: str = os.getenv("STREAMLIT_BASE_URL", "")
    api_base_url: str = os.getenv("API_BASE_URL", "")

    google_sheet_id: str = os.getenv("GOOGLE_SHEET_ID", "")
    google_service_account_json: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")

    line_channel_secret: str = _get_secret("LINE_CHANNEL_SECRET")
    line_channel_access_token: str = _get_secret("LINE_CHANNEL_ACCESS_TOKEN")

    teams_webhook_url: str = os.getenv("TEAMS_WEBHOOK_URL", "")
    outlook_webhook_url: str = os.getenv("OUTLOOK_WEBHOOK_URL", "")
    m365_webhook_token: str = os.getenv("M365_WEBHOOK_TOKEN", "")

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
