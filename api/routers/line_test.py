from __future__ import annotations

import hmac
import json
import os
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from config.settings import get_settings


router = APIRouter(prefix="/api/line-notifications", tags=["LINE Notifications"])
TAIPEI = ZoneInfo("Asia/Taipei")
LINE_BROADCAST_URL = "https://api.line.me/v2/bot/message/broadcast"


class LineMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)


class LineTestRequest(BaseModel):
    message: str = Field(
        default="開發工程部平台 LINE 通知測試成功。",
        min_length=1,
        max_length=1000,
    )


def _verify_token(
    received_token: str | None,
    authorization: str | None,
) -> None:
    expected = get_settings().m365_webhook_token.strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Render 尚未設定 M365_WEBHOOK_TOKEN。",
        )

    supplied = str(received_token or "").strip()
    if not supplied and authorization:
        scheme, _, credentials = authorization.partition(" ")
        if scheme.casefold() == "bearer":
            supplied = credentials.strip()

    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="通知 Token 無效。",
        )


def _line_access_token() -> str:
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Render 尚未設定 LINE_CHANNEL_ACCESS_TOKEN。",
        )
    return token


def _broadcast(message: str) -> dict:
    access_token = _line_access_token()
    now = datetime.now(TAIPEI).strftime("%Y-%m-%d %H:%M:%S")
    body = {
        "messages": [{"type": "text", "text": message.strip()[:5000]}],
        "notificationDisabled": False,
    }
    request = Request(
        LINE_BROADCAST_URL,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=15) as response:
            request_id = response.headers.get("x-line-request-id", "")
            response_status = response.status
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LINE API 回應失敗（HTTP {exc.code}）：{detail}",
        ) from exc
    except (URLError, TimeoutError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"無法連線 LINE API：{exc}",
        ) from exc

    return {
        "status": "ok",
        "delivery": "broadcast",
        "line_status_code": response_status,
        "line_request_id": request_id,
        "sent_at": now,
    }


@router.get("/status")
def line_status():
    return {
        "status": "ok",
        "configured": bool(os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()),
        "channel_access_token": bool(
            os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
        ),
        "channel_secret": bool(os.getenv("LINE_CHANNEL_SECRET", "").strip()),
    }


@router.post("/send")
def send_line_notification(
    payload: LineMessageRequest,
    x_m365_webhook_token: str | None = Header(
        default=None,
        alias="X-M365-Webhook-Token",
    ),
    authorization: str | None = Header(default=None),
):
    """Relay a platform notification through Render to LINE."""
    _verify_token(x_m365_webhook_token, authorization)
    result = _broadcast(payload.message)
    result["message"] = "LINE 通知已送出。"
    return result


@router.post("/test")
def send_line_test(
    payload: LineTestRequest,
    x_m365_webhook_token: str | None = Header(
        default=None,
        alias="X-M365-Webhook-Token",
    ),
    authorization: str | None = Header(default=None),
):
    _verify_token(x_m365_webhook_token, authorization)
    now = datetime.now(TAIPEI).strftime("%Y-%m-%d %H:%M:%S")
    result = _broadcast(
        f"【開發工程部平台】\n{payload.message.strip()}\n測試時間：{now}"
    )
    result["message"] = "LINE 測試通知已送出。"
    return result
