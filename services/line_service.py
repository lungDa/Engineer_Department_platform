import base64
import hashlib
import hmac
from typing import Any

import requests

from config.settings import get_runtime_secret
from services.base_service import BaseService
from shared.response import failed, success


class LineService(BaseService):
    """LINE Official Account messaging with a Render relay fallback."""

    service_name = "line"

    REPLY_ENDPOINT = "https://api.line.me/v2/bot/message/reply"
    PUSH_ENDPOINT = "https://api.line.me/v2/bot/message/push"
    BROADCAST_ENDPOINT = "https://api.line.me/v2/bot/message/broadcast"
    DEFAULT_API_BASE_URL = "https://engineer-department-platform.onrender.com"

    @staticmethod
    def _runtime_secret(name: str, default: str = "") -> str:
        """Read Streamlit Secrets/environment variables for every send."""
        return get_runtime_secret(name, default).strip()

    def is_configured(self) -> bool:
        return bool(
            self._runtime_secret("LINE_CHANNEL_ACCESS_TOKEN")
            or (
                self._relay_url()
                and self._runtime_secret("M365_WEBHOOK_TOKEN")
            )
        )

    def get_status(self) -> dict:
        direct_token = self._runtime_secret("LINE_CHANNEL_ACCESS_TOKEN")
        relay_token = self._runtime_secret("M365_WEBHOOK_TOKEN")
        return {
            "configured": self.is_configured(),
            "direct_token": bool(direct_token),
            "render_relay": bool(self._relay_url() and relay_token),
            "credential_diagnostics": {
                "m365_webhook_token_loaded": bool(relay_token),
                "api_base_url_loaded": bool(
                    self._runtime_secret("API_BASE_URL")
                ),
            },
            "features": {
                "webhook": True,
                "signature_validation": True,
                "reply": True,
                "push": True,
                "broadcast": True,
                "rich_menu": False,
            },
        }

    def _headers(self) -> dict[str, str]:
        token = self._runtime_secret("LINE_CHANNEL_ACCESS_TOKEN")
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

    def _relay_url(self) -> str:
        base_url = self._runtime_secret(
            "API_BASE_URL",
            self.DEFAULT_API_BASE_URL,
        )
        return f"{base_url.rstrip('/')}/api/line-notifications/send"

    def validate_signature(self, body: bytes, signature: str | None) -> bool:
        secret = self._runtime_secret("LINE_CHANNEL_SECRET")
        if not secret or not signature:
            return False
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
        expected = base64.b64encode(digest).decode("utf-8")
        return hmac.compare_digest(expected, signature)

    def reply_text(self, reply_token: str, text: str) -> dict:
        if not self._runtime_secret("LINE_CHANNEL_ACCESS_TOKEN"):
            return failed("LINE 回覆需要在執行環境設定 Channel Access Token。")
        if not reply_token:
            return failed("缺少 LINE reply_token。")
        return self._post_direct(
            self.REPLY_ENDPOINT,
            {
                "replyToken": reply_token,
                "messages": [{"type": "text", "text": str(text or "")[:5000]}],
            },
            "reply",
        )

    def push_text(self, user_id: str, text: str) -> dict:
        if not self._runtime_secret("LINE_CHANNEL_ACCESS_TOKEN"):
            return failed("LINE 個人推播需要在執行環境設定 Channel Access Token。")
        if not user_id:
            return failed("缺少 LINE user_id。")
        return self._post_direct(
            self.PUSH_ENDPOINT,
            {
                "to": user_id,
                "messages": [{"type": "text", "text": str(text or "")[:5000]}],
            },
            "push",
        )

    def _post_direct(self, endpoint: str, payload: dict, action: str) -> dict:
        try:
            response = requests.post(
                endpoint,
                headers=self._headers(),
                json=payload,
                timeout=15,
            )
            if response.status_code >= 400:
                self.logger.error(
                    "LINE %s failed: %s %s",
                    action,
                    response.status_code,
                    response.text,
                )
                return failed(
                    f"LINE {action} failed: {response.status_code}",
                    response.text,
                )
            return success(
                {"status_code": response.status_code},
                f"LINE {action} sent.",
            )
        except Exception as exc:
            self.logger.exception("LINE %s exception.", action)
            return failed(f"LINE {action} exception: {exc}")

    def _broadcast_direct(self, text: str) -> dict:
        payload = {
            "messages": [{"type": "text", "text": str(text or "")[:5000]}],
            "notificationDisabled": False,
        }
        return self._post_direct(self.BROADCAST_ENDPOINT, payload, "broadcast")

    def _broadcast_via_render(self, text: str) -> dict:
        relay_token = self._runtime_secret("M365_WEBHOOK_TOKEN")
        if not relay_token:
            return failed(
                "Streamlit 執行時未讀到 M365_WEBHOOK_TOKEN，"
                "無法呼叫 Render LINE 通知。",
                {
                    "m365_webhook_token_loaded": False,
                    "api_base_url_loaded": bool(
                        self._runtime_secret("API_BASE_URL")
                    ),
                },
            )

        try:
            response = requests.post(
                self._relay_url(),
                headers={
                    "Content-Type": "application/json",
                    "X-M365-Webhook-Token": relay_token,
                },
                json={"message": str(text or "")[:5000]},
                timeout=30,
            )
            if response.status_code >= 400:
                detail = response.text[:1000]
                self.logger.error(
                    "Render LINE relay failed: %s %s",
                    response.status_code,
                    detail,
                )
                return failed(
                    f"Render LINE 通知失敗：HTTP {response.status_code}",
                    detail,
                )
            data = response.json()
            return success(data, "LINE 已由 Render 發送。")
        except Exception as exc:
            self.logger.exception("Render LINE relay exception.")
            return failed(f"Render LINE 通知連線失敗：{exc}")

    def broadcast_text(self, text: str) -> dict:
        if self._runtime_secret("LINE_CHANNEL_ACCESS_TOKEN"):
            return self._broadcast_direct(text)
        return self._broadcast_via_render(text)

    def extract_text_events(self, payload: dict[str, Any]) -> list[dict]:
        events = []
        for event in payload.get("events", []):
            if event.get("type") != "message":
                continue
            message = event.get("message", {})
            if message.get("type") != "text":
                continue
            source = event.get("source", {})
            events.append(
                {
                    "reply_token": event.get("replyToken"),
                    "user_id": source.get("userId"),
                    "text": message.get("text", ""),
                    "timestamp": event.get("timestamp"),
                }
            )
        return events


line_service = LineService()
