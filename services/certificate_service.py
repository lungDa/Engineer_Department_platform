"""Certificate records stored in the Certificates Google Sheet."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from services.sheet_db import SheetDB


class CertificateService:
    WORKSHEET_NAME = "Certificates"
    COLUMNS = [
        "id", "account", "name", "certificate_name", "certificate_number",
        "issuer", "retraining_frequency", "issue_date", "retraining_date",
        "expiry_date", "notify_enabled", "notify_people", "notify_channels",
        "reminder_days", "notes", "created_at", "updated_at",
    ]

    @staticmethod
    def load_all() -> list[dict[str, Any]]:
        return SheetDB.load(CertificateService.WORKSHEET_NAME, CertificateService.COLUMNS, []) or []

    @staticmethod
    def add(record: dict[str, Any]) -> bool:
        rows = CertificateService.load_all()
        next_id = max([CertificateService.to_int(row.get("id")) for row in rows], default=0) + 1
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        row = {column: record.get(column, "") for column in CertificateService.COLUMNS}
        row.update({"id": next_id, "created_at": now, "updated_at": now})
        row["notify_enabled"] = "TRUE" if bool(record.get("notify_enabled")) else "FALSE"
        row["notify_people"] = CertificateService.list_json(record.get("notify_people", []))
        row["notify_channels"] = CertificateService.list_json(record.get("notify_channels", []))
        for field in ("issue_date", "retraining_date", "expiry_date"):
            row[field] = CertificateService.date_text(record.get(field))
        return SheetDB.append(CertificateService.WORKSHEET_NAME, CertificateService.COLUMNS, row)

    @staticmethod
    def delete(record_id: int) -> bool:
        target = CertificateService.to_int(record_id)
        rows = [row for row in CertificateService.load_all() if CertificateService.to_int(row.get("id")) != target]
        return SheetDB.save(CertificateService.WORKSHEET_NAME, CertificateService.COLUMNS, rows)

    @staticmethod
    def date_text(value: Any) -> str:
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value or "").strip()[:10]

    @staticmethod
    def parse_date(value: Any) -> date | None:
        try:
            return datetime.strptime(CertificateService.date_text(value), "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None

    @staticmethod
    def parse_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        try:
            parsed = json.loads(str(value or "[]"))
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
        return [item.strip() for item in str(value or "").replace("；", ",").split(",") if item.strip()]

    @staticmethod
    def list_json(value: Any) -> str:
        return json.dumps(CertificateService.parse_list(value), ensure_ascii=False)

    @staticmethod
    def to_int(value: Any, default: int = 0) -> int:
        try:
            return int(float(value or default))
        except (TypeError, ValueError):
            return default
