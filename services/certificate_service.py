"""Certificate records stored in the Certificates Google Sheet."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from services.sheet_db import SheetDB


class CertificateService:
    WORKSHEET_NAME = "Certificates"
    CERTIFICATE_DEFAULTS = {
        "職業安全管理師": {"category": "職安", "retraining_frequency": "12HR/2年"},
        "職業衛生管理師": {"category": "職安", "retraining_frequency": "12HR/2年"},
        "職業安全衛生管理員": {"category": "職安", "retraining_frequency": "12HR/2年"},
        "甲種職業安全衛生業務主管": {"category": "職安", "retraining_frequency": "6HR/2年"},
        "乙種職業安全衛生業務主管": {"category": "職安", "retraining_frequency": "6HR/2年"},
        "丙種職業安全衛生業務主管": {"category": "職安", "retraining_frequency": "6HR/2年"},
        "營造甲種業務主管": {"category": "職安", "retraining_frequency": "6HR/2年"},
        "營造乙種業務主管": {"category": "職安", "retraining_frequency": "6HR/2年"},
        "營造丙種業務主管": {"category": "職安", "retraining_frequency": "6HR/2年"},
        "一般安全衛生教育訓練(6小時)": {"category": "職安", "retraining_frequency": "3HR/3年"},
        "營造一般安全衛生教育訓練(6小時)": {"category": "職安", "retraining_frequency": "3HR/3年"},
        "特定化學物質作業主管": {"category": "作業主管", "retraining_frequency": "6HR/3年"},
        "缺氧作業主管": {"category": "作業主管", "retraining_frequency": "6HR/3年"},
        "有機溶劑作業主管": {"category": "作業主管", "retraining_frequency": "6HR/3年"},
        "粉塵作業主管": {"category": "作業主管", "retraining_frequency": "6HR/3年"},
        "屋頂作業主管": {"category": "作業主管", "retraining_frequency": "6HR/3年"},
        "急救人員": {"category": "操作人員", "retraining_frequency": "3HR/3年"},
        "堆高機操作": {"category": "操作人員", "retraining_frequency": "3HR/3年"},
        "高空工作車操作人員": {"category": "操作人員", "retraining_frequency": "3HR/3年"},
    }
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
