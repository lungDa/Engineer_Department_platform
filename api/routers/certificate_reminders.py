from __future__ import annotations

import hmac
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException, status

from config.settings import get_settings
from services.certificate_service import CertificateService
from services.notification_service import notification_service
from services.sheet_db import SheetDB


router = APIRouter(prefix="/api/certificates/reminders", tags=["Certificate Reminders"])
TAIPEI = ZoneInfo("Asia/Taipei")
LOG_WORKSHEET = "NotificationLogs"
LOG_COLUMNS = ["id", "event_key", "event_type", "entity_id", "channel", "sent_at", "status"]


def _verify_token(received_token: str | None, authorization: str | None) -> None:
    expected = get_settings().m365_webhook_token.strip()
    supplied = str(received_token or "").strip()
    if not supplied and authorization:
        scheme, _, credentials = authorization.partition(" ")
        if scheme.casefold() == "bearer":
            supplied = credentials.strip()
    if not expected:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Render 尚未設定 M365_WEBHOOK_TOKEN。")
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="證照提醒 Token 無效。")


@router.post("/run")
def run_certificate_reminders(
    x_m365_webhook_token: str | None = Header(default=None, alias="X-M365-Webhook-Token"),
    authorization: str | None = Header(default=None),
):
    _verify_token(x_m365_webhook_token, authorization)
    today = datetime.now(TAIPEI).date()
    logs = SheetDB.load(LOG_WORKSHEET, LOG_COLUMNS, []) or []
    sent_keys = {
        str(row.get("event_key") or "") for row in logs
        if str(row.get("status") or "").casefold() == "sent"
    }
    results = []
    for certificate in CertificateService.load_all():
        if str(certificate.get("notify_enabled") or "").upper() != "TRUE":
            continue
        expiry = CertificateService.parse_date(certificate.get("expiry_date"))
        reminder_days = CertificateService.to_int(certificate.get("reminder_days"), 30)
        if not expiry or not (0 <= (expiry - today).days <= reminder_days):
            continue
        certificate_id = CertificateService.to_int(certificate.get("id"))
        people = CertificateService.parse_list(certificate.get("notify_people"))
        channels = CertificateService.parse_list(certificate.get("notify_channels"))
        for channel in channels:
            event_key = f"certificate:{certificate_id}:expiry:{expiry.isoformat()}:{channel}"
            if event_key in sent_keys:
                results.append({"certificate_id": certificate_id, "channel": channel, "status": "skipped_duplicate"})
                continue
            notification = notification_service.send_certificate_expiry(
                certificate=certificate,
                recipient_names=people,
                channels=[channel],
            )
            channel_result = ((notification.get("data") or {}).get("channels") or {}).get(channel, {})
            result_status = "failed"
            if channel_result.get("ok") and not channel_result.get("skipped"):
                next_id = max([CertificateService.to_int(row.get("id")) for row in logs], default=0) + 1
                log = {
                    "id": next_id,
                    "event_key": event_key,
                    "event_type": "certificate_expiry",
                    "entity_id": certificate_id,
                    "channel": channel,
                    "sent_at": datetime.now(TAIPEI).strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "sent",
                }
                if SheetDB.append(LOG_WORKSHEET, LOG_COLUMNS, log):
                    logs.append(log)
                    sent_keys.add(event_key)
                    result_status = "sent"
            elif channel_result.get("skipped"):
                result_status = "skipped"
            results.append({
                "certificate_id": certificate_id,
                "name": certificate.get("name", ""),
                "certificate_name": certificate.get("certificate_name", ""),
                "channel": channel,
                "status": result_status,
                "message": channel_result.get("message", ""),
            })
    return {"status": "ok", "today": today.isoformat(), "results": results}
