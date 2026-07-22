from typing import Any

import requests

from config.settings import get_settings
from services.base_service import BaseService
from shared.response import failed, success


class TeamsService(BaseService):
    """Send notifications to a Power Automate Teams webhook flow."""

    service_name = "teams"

    def is_configured(self) -> bool:
        return bool(get_settings().teams_webhook_url.strip())

    def get_status(self) -> dict:
        return {
            "configured": self.is_configured(),
            "features": {"channel_notification": True, "power_automate": True},
        }

    def send(
        self,
        title: str,
        message: str,
        level: str = "info",
        facts: dict[str, Any] | None = None,
        source_url: str = "",
    ) -> dict:
        settings = get_settings()
        if not self.is_configured():
            return failed("Teams Power Automate Webhook 尚未設定。")
        if not title or not message:
            return failed("Teams 通知缺少標題或內容。")

        payload = {
            "title": str(title)[:200],
            "message": str(message)[:5000],
            "level": str(level or "info")[:20],
            "facts": facts or {},
            "source_url": str(source_url or "")[:2000],
            "system": settings.app_name,
            "version": settings.app_version,
        }
        headers = {"Content-Type": "application/json"}
        if settings.m365_webhook_token:
            headers["X-Platform-Token"] = settings.m365_webhook_token

        try:
            response = requests.post(
                settings.teams_webhook_url,
                headers=headers,
                json=payload,
                timeout=15,
            )
            if response.status_code >= 400:
                self.logger.error("Teams webhook failed: HTTP %s", response.status_code)
                return failed(
                    f"Teams 通知失敗：HTTP {response.status_code}",
                    {"status_code": response.status_code},
                )
            return success({"status_code": response.status_code}, "Teams 通知已送出。")
        except requests.RequestException as exc:
            self.logger.exception("Teams webhook exception.")
            return failed(f"Teams 通知連線失敗：{exc.__class__.__name__}")


teams_service = TeamsService()
