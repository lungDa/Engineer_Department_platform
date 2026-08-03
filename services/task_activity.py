from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

import streamlit as st

from services.sheet_db import SheetDB


class TaskActivityService:
    """任務留言與不可變操作歷程。每個事件各占 Google Sheet 一列。"""

    WORKSHEET_NAME = "TaskActivity"
    COLUMNS = [
        "id", "task_id", "event_type", "actor", "actor_account",
        "comment", "summary", "changes", "created_at",
    ]

    EVENT_LABELS = {
        "created": "建立任務",
        "updated": "修改任務",
        "checklist_updated": "更新子項目",
        "commented": "新增留言",
        "attachment_uploaded": "上傳附件",
        "attachment_deleted": "刪除附件",
        "deleted": "刪除任務",
    }

    FIELD_LABELS = {
        "title": "任務名稱", "category": "任務狀態", "due": "截止日期",
        "assignees": "指派人員", "progress": "進度", "hours_spent": "累計工時",
        "department": "部門", "importance": "重要度", "urgency": "緊急度",
        "tags": "標籤", "notes": "備註", "checklist": "子項目",
        "status": "資料狀態",
    }

    @staticmethod
    def default_rows() -> list[dict[str, Any]]:
        return []

    @staticmethod
    def _text(value: Any) -> str:
        if isinstance(value, (date, datetime)):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, list):
            if value and all(isinstance(item, dict) for item in value):
                completed = sum(bool(item.get("completed")) for item in value)
                return f"{completed}/{len(value)} 完成"
            return "、".join(str(item) for item in value)
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return str(value if value not in (None, "") else "—")

    @classmethod
    def build_changes(cls, before: dict[str, Any], changes: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        details: dict[str, Any] = {}
        parts: list[str] = []
        for field, new_value in changes.items():
            if field not in cls.FIELD_LABELS:
                continue
            old_value = before.get(field)
            old_text = cls._text(old_value)
            new_text = cls._text(new_value)
            if old_text == new_text:
                continue
            label = cls.FIELD_LABELS[field]
            details[field] = {"before": old_value, "after": new_value}
            parts.append(f"{label}：{old_text} → {new_text}")
        return "；".join(parts) or "資料已儲存（內容無差異）", details

    @classmethod
    def record(
        cls,
        task_id: Any,
        event_type: str,
        actor: str,
        actor_account: str = "",
        comment: str = "",
        summary: str = "",
        changes: dict[str, Any] | None = None,
    ) -> bool:
        rows = SheetDB.load(cls.WORKSHEET_NAME, cls.COLUMNS, cls.default_rows()) or []
        next_id = max((int(float(row.get("id") or 0)) for row in rows), default=0) + 1
        row = {
            "id": next_id,
            "task_id": int(float(task_id or 0)),
            "event_type": event_type,
            "actor": str(actor or "系統").strip(),
            "actor_account": str(actor_account or "").strip(),
            "comment": str(comment or "").strip(),
            "summary": str(summary or cls.EVENT_LABELS.get(event_type, event_type)).strip(),
            "changes": json.dumps(changes or {}, ensure_ascii=False, default=str),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        ok = SheetDB.append(cls.WORKSHEET_NAME, cls.COLUMNS, row)
        if not ok:
            fallback = st.session_state.setdefault("task_activity_fallback", [])
            fallback.append(row)
        return ok

    @classmethod
    def load_for_task(cls, task_id: Any) -> list[dict[str, Any]]:
        rows = SheetDB.load(cls.WORKSHEET_NAME, cls.COLUMNS, cls.default_rows())
        if rows is None:
            rows = st.session_state.get("task_activity_fallback", [])
        target = int(float(task_id or 0))
        result = [row for row in rows if int(float(row.get("task_id") or 0)) == target]
        return sorted(result, key=lambda row: (str(row.get("created_at", "")), int(float(row.get("id") or 0))))

    @classmethod
    def add_comment(cls, task_id: Any, actor: str, actor_account: str, comment: str) -> None:
        content = str(comment or "").strip()
        if not content:
            raise ValueError("留言內容不可空白。")
        if len(content) > 2000:
            raise ValueError("留言最多 2000 字。")
        if not cls.record(task_id, "commented", actor, actor_account, comment=content, summary="新增留言"):
            raise RuntimeError(st.session_state.get("sheet_db_error", "留言寫入失敗。"))
