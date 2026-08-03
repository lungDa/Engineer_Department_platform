"""Persist developer-managed feature switches in Google Sheet."""

from __future__ import annotations

from datetime import datetime

from services.sheet_db import SheetDB


class FeatureFlagService:
    SHEET_NAME = "FeatureFlags"
    COLUMNS = ["功能類別", "功能名稱", "狀態", "更新者", "更新時間"]

    @classmethod
    def load(cls, defaults: dict[str, dict[str, str]], force_refresh: bool = False) -> dict[str, dict[str, str]]:
        default_rows = [
            {
                "功能類別": category,
                "功能名稱": name,
                "狀態": status,
                "更新者": "系統預設",
                "更新時間": "",
            }
            for category, features in defaults.items()
            for name, status in features.items()
        ]
        records = SheetDB.load(
            cls.SHEET_NAME,
            cls.COLUMNS,
            default_rows,
            force_refresh=force_refresh,
        )
        if records is None:
            return {category: dict(features) for category, features in defaults.items()}

        saved = {
            str(row.get("功能名稱", "")).strip(): str(row.get("狀態", "")).strip().upper()
            for row in records
            if str(row.get("狀態", "")).strip().upper() in {"ON", "OFF"}
        }
        return {
            category: {name: saved.get(name, status) for name, status in features.items()}
            for category, features in defaults.items()
        }

    @classmethod
    def save(cls, settings: dict[str, dict[str, str]], updated_by: str) -> tuple[bool, str]:
        invalid = [
            f"{category}／{name}"
            for category, features in settings.items()
            for name, status in features.items()
            if str(status).upper() not in {"ON", "OFF"}
        ]
        if invalid:
            return False, "功能狀態只接受 ON 或 OFF：" + "、".join(invalid)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = [
            {
                "功能類別": category,
                "功能名稱": name,
                "狀態": str(status).upper(),
                "更新者": updated_by or "開發者",
                "更新時間": now,
            }
            for category, features in settings.items()
            for name, status in features.items()
        ]
        if not SheetDB.save(cls.SHEET_NAME, cls.COLUMNS, rows):
            return False, "儲存失敗，請檢查 Google Sheet 連線與編輯權限。"
        return True, "功能開關已儲存並立即套用。"

