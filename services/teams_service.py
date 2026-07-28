import re
from typing import Any, Iterable

import requests

from config.settings import get_settings
from services.base_service import BaseService
from shared.response import failed, success


class TeamsService(BaseService):
    """Send notifications to a Power Automate Teams webhook flow."""

    service_name = "teams"
    _UPN_PATTERN = re.compile(
        r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        re.IGNORECASE,
    )

    def is_configured(self) -> bool:
        return bool(get_settings().teams_webhook_url.strip())

    def is_bulletin_configured(self) -> bool:
        """Return whether the bulletin-only Teams webhook is configured."""
        return bool(get_settings().bulletin_webhook_url.strip())

    def get_status(self) -> dict:
        return {
            "configured": self.is_configured(),
            "bulletin_configured": self.is_bulletin_configured(),
            "features": {
                "channel_notification": True,
                "bulletin_channel_notification": True,
                "power_automate": True,
            },
        }

    def send(
        self,
        title: str,
        message: str,
        recipients: Iterable[str] | None = None,
        level: str = "info",
        facts: dict[str, Any] | None = None,
        source_url: str = "",
    ) -> dict:
        """Send one personal Teams message to every M365 recipient."""
        settings = get_settings()
        if not self.is_configured():
            return failed("Teams Power Automate Webhook 尚未設定。")

        targets = list(dict.fromkeys(
            str(recipient).strip()
            for recipient in (recipients or [])
            if str(recipient).strip()
        ))
        if not targets:
            return failed("Teams 通知失敗：被通知者尚未設定 M365 Email。")

        invalid_targets = [
            target for target in targets
            if not self._UPN_PATTERN.fullmatch(target)
        ]
        if invalid_targets:
            invalid_text = "、".join(invalid_targets)
            self.logger.warning(
                "Teams 個別通知未送出：M365 UPN 格式錯誤 | recipients=%s",
                invalid_text,
            )
            return failed(
                f"Teams 通知未送出：M365 UPN 格式錯誤（{invalid_text}）。"
                "請至人員名單後台修正。",
                {"invalid_recipients": invalid_targets},
            )

        message_lines = [str(message).strip()]
        message_lines.extend(
            f"{key}：{value}"
            for key, value in (facts or {}).items()
            if str(value).strip()
        )
        if source_url:
            message_lines.append(f"開啟管理平台：{source_url}")
        personal_message = "\n".join(line for line in message_lines if line)

        deliveries = [
            {
                "recipient": recipient,
                "result": self._post_json(
                    webhook_url=settings.teams_webhook_url,
                    payload={
                        "recipient": recipient,
                        "title": str(title)[:200],
                        "message": personal_message[:5000],
                    },
                    failure_label="Teams 個別通知",
                ),
            }
            for recipient in targets
        ]
        failed_deliveries = [
            delivery for delivery in deliveries
            if not delivery["result"].get("ok")
        ]
        if failed_deliveries:
            return failed(
                "Teams 個別通知部分或全部失敗。",
                {
                    "deliveries": deliveries,
                    "failed_recipients": [
                        delivery["recipient"] for delivery in failed_deliveries
                    ],
                },
            )
        return success(
            {"deliveries": deliveries},
            f"Teams 已個別通知 {len(deliveries)} 人。",
        )

    def send_bulletin(
        self,
        title: str,
        message: str,
        level: str = "info",
        facts: dict[str, Any] | None = None,
        source_url: str = "",
    ) -> dict:
        """Send a bulletin only to the dedicated Teams bulletin channel."""
        settings = get_settings()
        if not self.is_bulletin_configured():
            return failed("Teams 布告欄專用 Webhook 尚未設定。")

        return self._send_to_webhook(
            webhook_url=settings.bulletin_webhook_url,
            title=title,
            message=message,
            level=level,
            facts=facts,
            source_url=source_url,
            success_message="Teams 布告欄通知已送出。",
            failure_label="Teams 布告欄通知",
        )

    def _send_to_webhook(
        self,
        *,
        webhook_url: str,
        title: str,
        message: str,
        level: str,
        facts: dict[str, Any] | None,
        source_url: str,
        success_message: str,
        failure_label: str,
    ) -> dict:
        settings = get_settings()
        if not title or not message:
            return failed(f"{failure_label}缺少標題或內容。")

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
            result = self._post_json(
                webhook_url=webhook_url,
                payload=payload,
                failure_label=failure_label,
                headers=headers,
            )
            if not result.get("ok"):
                return result
            return success(result.get("data"), success_message)
        except requests.RequestException as exc:
            self.logger.exception("%s webhook exception.", failure_label)
            return failed(f"{failure_label}連線失敗：{exc.__class__.__name__}")

    def _post_json(
        self,
        *,
        webhook_url: str,
        payload: dict[str, Any],
        failure_label: str,
        headers: dict[str, str] | None = None,
    ) -> dict:
        request_headers = {"Content-Type": "application/json"}
        request_headers.update(headers or {})
        try:
            response = requests.post(
                webhook_url,
                headers=request_headers,
                json=payload,
                timeout=15,
            )
            response_excerpt = response.text[:1000]
            if response.status_code >= 400:
                self.logger.error(
                    "%s webhook failed: HTTP %s | response=%s",
                    failure_label,
                    response.status_code,
                    response_excerpt or "(empty)",
                )
                return failed(
                    f"{failure_label}失敗：HTTP {response.status_code}",
                    {
                        "status_code": response.status_code,
                        "response": response_excerpt,
                    },
                )
            return success(
                {
                    "status_code": response.status_code,
                    "response": response_excerpt,
                },
                f"{failure_label}已送出。",
            )
        except requests.RequestException as exc:
            self.logger.exception("%s webhook exception.", failure_label)
            return failed(f"{failure_label}連線失敗：{exc.__class__.__name__}")


teams_service = TeamsService()
