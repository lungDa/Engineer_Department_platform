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

        fact_rows = [
            {"title": str(key)[:100], "value": str(value)[:500]}
            for key, value in (facts or {}).items()
        ]
        fact_rows.extend(
            [
                {"title": "系統", "value": settings.app_name},
                {"title": "版本", "value": settings.app_version},
            ]
        )

        # The Teams Workflows template "Send webhook alerts to a channel"
        # expects a message envelope containing an Adaptive Card. A custom
        # title/message JSON body can reach the flow trigger but cannot be
        # rendered by its "Post card in a chat or channel" action.
        card_body: list[dict[str, Any]] = [
            {
                "type": "TextBlock",
                "text": str(title)[:200],
                "weight": "Bolder",
                "size": "Medium",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": str(message)[:5000],
                "wrap": True,
            },
            {
                "type": "FactSet",
                "facts": fact_rows,
            },
        ]
        if source_url:
            card_body.append(
                {
                    "type": "ActionSet",
                    "actions": [
                        {
                            "type": "Action.OpenUrl",
                            "title": "開啟管理平台",
                            "url": str(source_url)[:2000],
                        }
                    ],
                }
            )

        payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "contentUrl": None,
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.2",
                        "body": card_body,
                    },
                }
            ],
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
                    {
                        "status_code": response.status_code,
                        "response": response.text[:500],
                    },
                )
            return success(
                {
                    "status_code": response.status_code,
                    "response": response.text[:500],
                },
                "Teams 通知已送出。",
            )
        except requests.RequestException as exc:
            self.logger.exception("Teams webhook exception.")
            return failed(f"Teams 通知連線失敗：{exc.__class__.__name__}")


teams_service = TeamsService()
