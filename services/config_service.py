from config.settings import get_settings
from services.base_service import BaseService


class ConfigService(BaseService):
    service_name = "config"

    def get_settings(self):
        return get_settings()

    def get_public_info(self) -> dict:
        settings = get_settings()
        return {
            "app_name": settings.app_name,
            "app_version": settings.app_version,
            "environment": settings.environment,
            "streamlit_base_url": settings.streamlit_base_url,
            "api_base_url": settings.api_base_url,
        }


config_service = ConfigService()
