from typing import Iterable

import requests

from config.settings import get_settings
from services.base_service import BaseService
from shared.response import failed, success


class MailService(BaseService):
    """Send Outlook mail through a Power Automate webhook flow."""

    service_name = "mail"

    def is_configured(self) -> bool:
        return bool(get_settings().outlook_webhook_url.strip())

    def get_status(self) -> dict:
        return {
            "configured": self.is_configured(),
            "features": {"send_mail": True, "power_automate": True},
        }

    @staticmethod
    def _recipients(value: str | Iterable[str]) -> list[str]:
        if isinstance(value, str):
            values = value.replace(",", ";").split(";")
        else:
            values = list(value)
        return [str(item).strip() for item in values if str(item).strip()]

    def send(
        self,
        to: str | Iterable[str],
        subject: str,
        body: str,
        cc: str | Iterable[str] = "",
        is_html: bool = False,
    ) -> dict:
        recipients = self._recipients(to)
        if not recipients:
            return failed("缺少收件者。")
        if not subject:
            return failed("缺少郵件主旨。")
        if not self.is_configured():
            return failed("Outlook Power Automate Webhook 尚未設定。")

        settings = get_settings()
        payload = {
            "to": recipients,
            "cc": self._recipients(cc),
            "subject": str(subject)[:500],
            "body": str(body or "")[:50000],
            "is_html": bool(is_html),
            "system": settings.app_name,
            "version": settings.app_version,
        }
        headers = {"Content-Type": "application/json"}
        if settings.m365_webhook_token:
            headers["X-Platform-Token"] = settings.m365_webhook_token

        try:
            response = requests.post(
                settings.outlook_webhook_url,
                headers=headers,
                json=payload,
                timeout=15,
            )
            if response.status_code >= 400:
                self.logger.error("Outlook webhook failed: HTTP %s", response.status_code)
                return failed(
                    f"Outlook 寄信失敗：HTTP {response.status_code}",
                    {"status_code": response.status_code},
                )
            return success({"status_code": response.status_code}, "Outlook 郵件已送出。")
        except requests.RequestException as exc:
            self.logger.exception("Outlook webhook exception.")
            return failed(f"Outlook 寄信連線失敗：{exc.__class__.__name__}")


mail_service = MailService()
