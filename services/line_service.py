import base64
import hashlib
import hmac
from typing import Any

import requests

from config.settings import get_settings
from services.base_service import BaseService
from shared.response import failed, success


class LineService(BaseService):
    """LINE Official Account service.

    V5.1.0 supports:
    - Signature validation
    - Reply text message
    - Push text message
    - Webhook event extraction
    """

    service_name = "line"

    REPLY_ENDPOINT = "https://api.line.me/v2/bot/message/reply"
    PUSH_ENDPOINT = "https://api.line.me/v2/bot/message/push"
    BROADCAST_ENDPOINT = "https://api.line.me/v2/bot/message/broadcast"

    def is_configured(self) -> bool:
        settings = get_settings()
        return bool(settings.line_channel_secret and settings.line_channel_access_token)

    def get_status(self) -> dict:
        return {
            "configured": self.is_configured(),
            "features": {
                "webhook": True,
                "signature_validation": True,
                "reply": True,
                "push": True,
                "rich_menu": False,
            },
        }

    def _headers(self) -> dict[str, str]:
        token = get_settings().line_channel_access_token
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

    def validate_signature(self, body: bytes, signature: str | None) -> bool:
        secret = get_settings().line_channel_secret

        if not secret or not signature:
            return False

        digest = hmac.new(
            secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).digest()

        expected = base64.b64encode(digest).decode("utf-8")
        return hmac.compare_digest(expected, signature)

    def reply_text(self, reply_token: str, text: str) -> dict:
        if not self.is_configured():
            return failed("LINE 尚未設定 Channel Secret / Access Token。")
        if not reply_token:
            return failed("缺少 LINE reply_token。")

        payload = {
            "replyToken": reply_token,
            "messages": [
                {
                    "type": "text",
                    "text": str(text or "")[:5000],
                }
            ],
        }

        try:
            response = requests.post(
                self.REPLY_ENDPOINT,
                headers=self._headers(),
                json=payload,
                timeout=10,
            )

            if response.status_code >= 400:
                self.logger.error("LINE reply failed: %s %s", response.status_code, response.text)
                return failed(f"LINE reply failed: {response.status_code}", response.text)

            return success({"status_code": response.status_code}, "LINE reply sent.")

        except Exception as exc:
            self.logger.exception("LINE reply exception.")
            return failed(f"LINE reply exception: {exc}")

    def push_text(self, user_id: str, text: str) -> dict:
        if not self.is_configured():
            return failed("LINE 尚未設定 Channel Secret / Access Token。")
        if not user_id:
            return failed("缺少 LINE user_id。")

        payload = {
            "to": user_id,
            "messages": [
                {
                    "type": "text",
                    "text": str(text or "")[:5000],
                }
            ],
        }

        try:
            response = requests.post(
                self.PUSH_ENDPOINT,
                headers=self._headers(),
                json=payload,
                timeout=10,
            )

            if response.status_code >= 400:
                self.logger.error("LINE push failed: %s %s", response.status_code, response.text)
                return failed(f"LINE push failed: {response.status_code}", response.text)

            return success({"status_code": response.status_code}, "LINE push sent.")

        except Exception as exc:
            self.logger.exception("LINE push exception.")
            return failed(f"LINE push exception: {exc}")

    def broadcast_text(self, text: str) -> dict:
        """Broadcast one event to every friend of the official account."""
        # Sending a broadcast only needs the channel access token. The channel
        # secret is required for validating inbound webhook signatures, not for
        # outbound broadcast requests.
        if not get_settings().line_channel_access_token:
            return failed("LINE 尚未設定 Channel Access Token。")

        payload = {
            "messages": [
                {
                    "type": "text",
                    "text": str(text or "")[:5000],
                }
            ],
            "notificationDisabled": False,
        }

        try:
            response = requests.post(
                self.BROADCAST_ENDPOINT,
                headers=self._headers(),
                json=payload,
                timeout=15,
            )
            request_id = response.headers.get("x-line-request-id", "")
            if response.status_code >= 400:
                self.logger.error(
                    "LINE broadcast failed: %s %s",
                    response.status_code,
                    response.text,
                )
                return failed(
                    f"LINE broadcast failed: {response.status_code}",
                    response.text,
                )
            return success(
                {
                    "status_code": response.status_code,
                    "request_id": request_id,
                    "delivery": "broadcast",
                },
                "LINE 官方帳號廣播已送出。",
            )
        except Exception as exc:
            self.logger.exception("LINE broadcast exception.")
            return failed(f"LINE broadcast exception: {exc}")

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
