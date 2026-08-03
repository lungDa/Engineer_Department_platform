from __future__ import annotations

import io
import json
import os
import re
import uuid
from datetime import datetime
from typing import Any

import requests
import streamlit as st
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials

from services.sheet_db import SheetDB
from services.task_activity import TaskActivityService
from config.功能開關 import 功能已開啟


class TaskAttachmentService:
    """Store task files in a private Google Drive folder and indexes in Sheets."""

    WORKSHEET_NAME = "TaskAttachments"
    COLUMNS = [
        "id", "task_id", "drive_file_id", "file_name", "mime_type", "size_bytes",
        "uploaded_by", "uploaded_account", "created_at", "status", "deleted_at",
    ]
    MAX_FILE_SIZE = 20 * 1024 * 1024
    ALLOWED_EXTENSIONS = {
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".csv", ".txt", ".zip", ".jpg", ".jpeg", ".png", ".webp",
        ".dwg", ".dxf",
    }

    @staticmethod
    def _folder_id() -> str:
        value = os.getenv("TASK_ATTACHMENT_FOLDER_ID", "").strip()
        try:
            value = value or str(st.secrets.get("TASK_ATTACHMENT_FOLDER_ID", "")).strip()
        except Exception:
            pass
        if not value:
            raise RuntimeError("尚未設定 TASK_ATTACHMENT_FOLDER_ID。")
        return value

    @staticmethod
    def _credentials() -> Credentials:
        info = SheetDB.get_service_account_info()
        ok, message = SheetDB._validate_service_account(info)
        if not ok:
            raise RuntimeError(message)
        credentials = Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/drive"],
        )
        credentials.refresh(Request())
        return credentials

    @classmethod
    def _request(cls, method: str, url: str, **kwargs):
        credentials = cls._credentials()
        headers = dict(kwargs.pop("headers", {}) or {})
        headers["Authorization"] = f"Bearer {credentials.token}"
        response = requests.request(method, url, headers=headers, timeout=120, **kwargs)
        if not response.ok:
            detail = response.text[:500]
            raise RuntimeError(f"Google Drive 操作失敗（HTTP {response.status_code}）：{detail}")
        return response

    @staticmethod
    def _safe_name(name: str) -> str:
        name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", str(name or "attachment"))
        return name.strip(" .")[:180] or "attachment"

    @classmethod
    def validate_file(cls, uploaded_file) -> tuple[str, bytes, str]:
        name = cls._safe_name(uploaded_file.name)
        extension = os.path.splitext(name)[1].lower()
        if extension not in cls.ALLOWED_EXTENSIONS:
            raise ValueError(f"不支援 {extension or '無副檔名'} 檔案。")
        data = uploaded_file.getvalue()
        if not data:
            raise ValueError("附件內容不可空白。")
        if len(data) > cls.MAX_FILE_SIZE:
            raise ValueError("單一附件不可超過 20 MB。")
        mime_type = str(getattr(uploaded_file, "type", "") or "application/octet-stream")
        return name, data, mime_type

    @classmethod
    def upload(cls, task_id: Any, uploaded_file, actor: str, account: str) -> dict[str, Any]:
        if not 功能已開啟("任務附件"):
            raise RuntimeError("任務附件功能目前已關閉。")
        name, data, mime_type = cls.validate_file(uploaded_file)
        metadata = {
            "name": f"task-{int(float(task_id))}-{uuid.uuid4().hex[:8]}-{name}",
            "parents": [cls._folder_id()],
            "appProperties": {"task_id": str(int(float(task_id))), "original_name": name},
        }
        response = cls._request(
            "POST",
            "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true&fields=id,name,size,mimeType",
            files={
                "metadata": (None, json.dumps(metadata, ensure_ascii=False), "application/json; charset=UTF-8"),
                "file": (name, io.BytesIO(data), mime_type),
            },
        )
        drive_file = response.json()
        rows = SheetDB.load(cls.WORKSHEET_NAME, cls.COLUMNS, []) or []
        next_id = max((int(float(row.get("id") or 0)) for row in rows), default=0) + 1
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = {
            "id": next_id,
            "task_id": int(float(task_id)),
            "drive_file_id": drive_file["id"],
            "file_name": name,
            "mime_type": mime_type,
            "size_bytes": len(data),
            "uploaded_by": actor,
            "uploaded_account": account,
            "created_at": now,
            "status": "Active",
            "deleted_at": "",
        }
        if not SheetDB.append(cls.WORKSHEET_NAME, cls.COLUMNS, row):
            try:
                cls._request("PATCH", f"https://www.googleapis.com/drive/v3/files/{drive_file['id']}?supportsAllDrives=true", json={"trashed": True})
            finally:
                raise RuntimeError(st.session_state.get("sheet_db_error", "附件索引寫入失敗。"))
        TaskActivityService.record(
            task_id, "attachment_uploaded", actor, account,
            summary=f"上傳附件：{name}（{cls.format_size(len(data))}）",
        )
        return row

    @classmethod
    def load_for_task(cls, task_id: Any) -> list[dict[str, Any]]:
        rows = SheetDB.load(cls.WORKSHEET_NAME, cls.COLUMNS, []) or []
        target = int(float(task_id or 0))
        result = [
            row for row in rows
            if int(float(row.get("task_id") or 0)) == target and str(row.get("status") or "Active") == "Active"
        ]
        return sorted(result, key=lambda row: (str(row.get("created_at", "")), int(float(row.get("id") or 0))))

    @classmethod
    def download(cls, attachment: dict[str, Any]) -> bytes:
        if not 功能已開啟("任務附件"):
            raise RuntimeError("任務附件功能目前已關閉。")
        file_id = str(attachment.get("drive_file_id") or "").strip()
        if not file_id:
            raise ValueError("附件缺少 Drive 檔案 ID。")
        return cls._request(
            "GET",
            f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&supportsAllDrives=true",
        ).content

    @classmethod
    def delete(cls, attachment_id: Any, task_id: Any, actor: str, account: str) -> None:
        if not 功能已開啟("任務附件"):
            raise RuntimeError("任務附件功能目前已關閉。")
        rows = SheetDB.load(cls.WORKSHEET_NAME, cls.COLUMNS, []) or []
        target = int(float(attachment_id or 0))
        selected = None
        for row in rows:
            if int(float(row.get("id") or 0)) == target and int(float(row.get("task_id") or 0)) == int(float(task_id or 0)):
                selected = row
                break
        if not selected or str(selected.get("status") or "Active") != "Active":
            raise ValueError("找不到要刪除的附件。")
        cls._request(
            "PATCH",
            f"https://www.googleapis.com/drive/v3/files/{selected['drive_file_id']}?supportsAllDrives=true",
            json={"trashed": True},
        )
        selected["status"] = "Deleted"
        selected["deleted_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not SheetDB.save(cls.WORKSHEET_NAME, cls.COLUMNS, rows):
            raise RuntimeError(st.session_state.get("sheet_db_error", "附件索引更新失敗。"))
        TaskActivityService.record(
            task_id, "attachment_deleted", actor, account,
            summary=f"刪除附件：{selected.get('file_name', '')}",
        )

    @staticmethod
    def format_size(value: Any) -> str:
        size = int(float(value or 0))
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"
