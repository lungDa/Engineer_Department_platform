import time
from datetime import datetime
from typing import Any

import requests

from config.settings import get_settings
from services.ai_service import ai_service
from services.line_service import line_service
from services.mail_service import mail_service
from services.sheet_db import SheetDB, SheetDiagnostics
from services.teams_service import teams_service
from shared.logger import get_logger

logger = get_logger(__name__)


class DiagnosticsService:
    """Enterprise diagnostics center service.

    This service is designed for Streamlit developer diagnostics.
    It does not expose secrets. It only reports configured / not configured.
    """

    REPORT_SCHEMA_VERSION = 2

    @staticmethod
    def mask_value(value: str | None, keep: int = 4) -> str:
        value = str(value or "").strip()
        if not value:
            return "未設定"
        if len(value) <= keep:
            return "*" * len(value)
        return f"{value[:keep]}...{value[-keep:]}"

    @staticmethod
    def google_sheet_status() -> dict[str, Any]:
        status = SheetDiagnostics.status()
        return {
            "name": "Google Sheet",
            "connected": bool(status.get("connected")),
            "sheet_id_present": bool(status.get("sheet_id_present")),
            "sheet_id": status.get("sheet_id", ""),
            "service_account_present": bool(status.get("service_account_present")),
            "service_account_valid": bool(status.get("service_account_valid")),
            "client_email": status.get("client_email", ""),
            "spreadsheet_title": status.get("spreadsheet_title", ""),
            "error": status.get("error", ""),
        }

    @staticmethod
    def line_status() -> dict[str, Any]:
        settings = get_settings()
        status = line_service.get_status()
        webhook_url = ""
        if settings.api_base_url:
            webhook_url = settings.api_base_url.rstrip("/") + "/api/line/webhook"

        return {
            "name": "LINE Official Account",
            "configured": bool(status.get("configured")),
            "channel_secret_present": bool(settings.line_channel_secret),
            "channel_access_token_present": bool(settings.line_channel_access_token),
            "channel_secret_masked": DiagnosticsService.mask_value(settings.line_channel_secret),
            "channel_access_token_masked": DiagnosticsService.mask_value(settings.line_channel_access_token),
            "webhook_url": webhook_url,
            "features": status.get("features", {}),
        }

    @staticmethod
    def microsoft365_status() -> dict[str, Any]:
        settings = get_settings()
        return {
            "name": "Microsoft 365 Notifications",
            "teams_configured": teams_service.is_configured(),
            "outlook_configured": mail_service.is_configured(),
            "teams_webhook_present": bool(settings.teams_webhook_url),
            "outlook_webhook_present": bool(settings.outlook_webhook_url),
            "webhook_token_present": bool(settings.m365_webhook_token),
            "teams_webhook_masked": DiagnosticsService.mask_value(settings.teams_webhook_url, keep=8),
            "outlook_webhook_masked": DiagnosticsService.mask_value(settings.outlook_webhook_url, keep=8),
            "features": {
                "teams_channel_notification": True,
                "outlook_send_mail": True,
                "event_triggers_connected": False,
            },
        }

    @staticmethod
    def render_api_status(timeout: int = 8) -> dict[str, Any]:
        settings = get_settings()
        base_url = settings.api_base_url.rstrip("/") if settings.api_base_url else ""
        result = {
            "name": "Render API",
            "configured": bool(base_url),
            "base_url": base_url,
            "health_url": base_url + "/health" if base_url else "",
            "ready_url": base_url + "/ready" if base_url else "",
            "health_ok": False,
            "ready_ok": False,
            "latency_ms": None,
            "version": settings.app_version,
            "environment": settings.environment,
            "error": "",
        }

        if not base_url:
            result["error"] = "API_BASE_URL 尚未設定。"
            return result

        start = time.time()
        try:
            response = requests.get(result["health_url"], timeout=timeout)
            result["latency_ms"] = round((time.time() - start) * 1000, 2)
            result["health_ok"] = response.status_code == 200
            if response.status_code == 200:
                payload = response.json()
                result["version"] = payload.get("version", result["version"])
            else:
                result["error"] = f"Health HTTP {response.status_code}: {response.text[:200]}"
        except Exception as exc:
            result["latency_ms"] = round((time.time() - start) * 1000, 2)
            result["error"] = str(exc)

        try:
            ready_response = requests.get(result["ready_url"], timeout=timeout)
            result["ready_ok"] = ready_response.status_code == 200
        except Exception:
            result["ready_ok"] = False

        return result

    @staticmethod
    def ai_status() -> dict[str, Any]:
        settings = get_settings()
        return {
            "name": "AI Service",
            "configured": ai_service.is_configured(),
            "openai_api_key_present": bool(settings.openai_api_key),
            "openai_api_key_masked": DiagnosticsService.mask_value(settings.openai_api_key),
            "features": {
                "chat": False,
                "task_analysis": False,
                "equipment_query": False,
            },
        }

    @staticmethod
    def system_report() -> dict[str, Any]:
        google = DiagnosticsService.google_sheet_status()
        line = DiagnosticsService.line_status()
        microsoft365 = DiagnosticsService.microsoft365_status()
        render = DiagnosticsService.render_api_status()
        ai = DiagnosticsService.ai_status()

        checks = [
            google.get("connected"),
            google.get("service_account_valid"),
            line.get("channel_secret_present"),
            line.get("channel_access_token_present"),
            microsoft365.get("teams_configured"),
            microsoft365.get("outlook_configured"),
            render.get("configured"),
            render.get("health_ok"),
            render.get("ready_ok"),
            ai.get("configured"),
        ]

        passed = sum(1 for item in checks if item)
        total = len(checks)
        score = round((passed / total) * 100) if total else 0

        return {
            "schema_version": DiagnosticsService.REPORT_SCHEMA_VERSION,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "score": score,
            "passed": passed,
            "total": total,
            "google_sheet": google,
            "line": line,
            "microsoft365": microsoft365,
            "render_api": render,
            "ai": ai,
        }

    @staticmethod
    def clear_cache() -> None:
        SheetDB.clear_cache()
