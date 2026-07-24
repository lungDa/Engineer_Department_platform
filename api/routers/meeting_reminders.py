from __future__ import annotations

import hmac
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from config.settings import get_settings
from services.core import MeetingService
from services.notification_service import notification_service
from services.sheet_db import SheetDB


router = APIRouter(
    prefix="/api/meetings/reminders",
    tags=["Meeting Reminders"],
)

TAIPEI = ZoneInfo("Asia/Taipei")
LOG_WORKSHEET = "NotificationLogs"
LOG_COLUMNS = [
    "id",
    "event_key",
    "event_type",
    "entity_id",
    "channel",
    "sent_at",
    "status",
]


class ReminderRunRequest(BaseModel):
    days_before: int = Field(default=1, ge=0, le=30)
    channels: list[str] = Field(
        default_factory=lambda: ["teams", "outlook"],
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
            detail="會議提醒 Token 無效。",
        )


def _load_logs() -> list[dict]:
    rows = SheetDB.load(LOG_WORKSHEET, LOG_COLUMNS, [])
    return rows or []


def _append_log(
    logs: list[dict],
    *,
    event_key: str,
    meeting_id: int,
    channel: str,
) -> None:
    next_id = max(
        [int(float(row.get("id") or 0)) for row in logs],
        default=0,
    ) + 1
    row = {
        "id": next_id,
        "event_key": event_key,
        "event_type": "meeting_reminder",
        "entity_id": meeting_id,
        "channel": channel,
        "sent_at": datetime.now(TAIPEI).strftime("%Y-%m-%d %H:%M:%S"),
        "status": "sent",
    }
    if not SheetDB.append(LOG_WORKSHEET, LOG_COLUMNS, row):
        raise RuntimeError("會議提醒已送出，但 NotificationLogs 寫入失敗。")
    logs.append(row)


@router.post("/run")
def run_meeting_reminders(
    request: ReminderRunRequest,
    x_m365_webhook_token: str | None = Header(
        default=None,
        alias="X-M365-Webhook-Token",
    ),
    authorization: str | None = Header(default=None),
):
    _verify_token(x_m365_webhook_token, authorization)

    allowed_channels = {"teams", "outlook"}
    channels = list(
        dict.fromkeys(
            str(channel).strip().lower()
            for channel in request.channels
            if str(channel).strip().lower() in allowed_channels
        )
    )
    if not channels:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="至少需要一個有效通知管道：teams 或 outlook。",
        )

    today = datetime.now(TAIPEI).date()
    target_date = today + timedelta(days=request.days_before)
    meetings = [
        meeting
        for meeting in MeetingService.load_all()
        if meeting.get("time") == target_date
    ]
    logs = _load_logs()
    sent_keys = {
        str(row.get("event_key") or "").strip()
        for row in logs
        if str(row.get("status") or "").strip().lower() == "sent"
    }

    results: list[dict] = []
    for meeting in meetings:
        meeting_id = int(meeting.get("id") or 0)
        for channel in channels:
            event_key = (
                f"meeting:{meeting_id}:reminder:"
                f"{target_date.isoformat()}:{channel}"
            )
            if event_key in sent_keys:
                results.append(
                    {
                        "meeting_id": meeting_id,
                        "title": meeting.get("title", ""),
                        "channel": channel,
                        "status": "skipped_duplicate",
                    }
                )
                continue

            notification_result = notification_service.send_meeting_event(
                event="reminder",
                meeting=meeting,
                actor="系統自動提醒",
                channels=[channel],
            )
            channel_result = (
                (notification_result.get("data") or {})
                .get("channels", {})
                .get(channel, {})
            )
            if channel_result.get("ok") and not channel_result.get("skipped"):
                _append_log(
                    logs,
                    event_key=event_key,
                    meeting_id=meeting_id,
                    channel=channel,
                )
                sent_keys.add(event_key)
                result_status = "sent"
            elif channel_result.get("skipped"):
                result_status = "skipped"
            else:
                result_status = "failed"

            results.append(
                {
                    "meeting_id": meeting_id,
                    "title": meeting.get("title", ""),
                    "channel": channel,
                    "status": result_status,
                    "message": channel_result.get("message", ""),
                }
            )

    return {
        "status": "ok",
        "today": today.isoformat(),
        "target_date": target_date.isoformat(),
        "days_before": request.days_before,
        "meeting_count": len(meetings),
        "results": results,
    }
