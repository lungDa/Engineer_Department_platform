import base64
import hashlib
import hmac
import re
from typing import Any

import requests

from config.settings import get_runtime_secret
from services.base_service import BaseService
from shared.response import failed, success
from config.功能開關 import 功能已開啟


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
        return 功能已開啟("LINE通知") and bool(
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
        if not 功能已開啟("LINE智慧助理"):
            return failed("LINE 智慧助理功能目前已關閉。")
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
        if not 功能已開啟("LINE通知"):
            return failed("LINE 通知功能目前已關閉。")
        if not self._runtime_secret("LINE_CHANNEL_ACCESS_TOKEN"):
            self.logger.error(
                "LINE push skipped: LINE_CHANNEL_ACCESS_TOKEN is missing in this runtime."
            )
            return failed(
                "目前執行 Streamlit 的環境未讀到 LINE_CHANNEL_ACCESS_TOKEN。",
                {"reason": "missing_access_token"},
            )
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id:
            self.logger.error("LINE push skipped: user_id is missing.")
            return failed("缺少 LINE User ID。", {"reason": "missing_user_id"})
        if not re.fullmatch(r"U[0-9a-fA-F]{32}", normalized_user_id):
            self.logger.error("LINE push skipped: invalid LINE User ID format.")
            return failed(
                "LINE User ID 格式錯誤（應為 U 開頭加 32 碼英數識別碼）；"
                "請至人員名單後台修正，本次資料不會被清除。",
                {"reason": "invalid_user_id_format"},
            )
        return self._post_direct(
            self.PUSH_ENDPOINT,
            {
                "to": normalized_user_id,
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
                    f"LINE API 回傳 {response.status_code}：{response.text[:1000]}",
                    {
                        "status_code": response.status_code,
                        "request_id": response.headers.get("x-line-request-id", ""),
                        "response": response.text[:1000],
                    },
                )
            self.logger.info(
                "LINE %s sent: status=%s request_id=%s",
                action,
                response.status_code,
                response.headers.get("x-line-request-id", ""),
            )
            return success(
                {
                    "status_code": response.status_code,
                    "request_id": response.headers.get("x-line-request-id", ""),
                },
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
        if not 功能已開啟("LINE通知"):
            return failed("LINE 通知功能目前已關閉。")
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
