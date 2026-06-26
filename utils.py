
import base64
import json
import os
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import streamlit as st


# =========================================================
# Google Sheet 共用層：讓所有功能匹配範本工作表
# =========================================================
class SheetDB:
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    @staticmethod
    def get_sheet_id():
        try:
            return st.secrets.get("google_sheet", {}).get("spreadsheet_id") or st.secrets.get("SHEET_ID")
        except Exception:
            return os.getenv("SHEET_ID")

    @staticmethod
    def get_service_account_info():
        try:
            return st.secrets.get("gcp_service_account", None)
        except Exception:
            return None

    @staticmethod
    @st.cache_resource(show_spinner=False)
    def spreadsheet():
        try:
            import gspread
            from google.oauth2.service_account import Credentials

            sheet_id = SheetDB.get_sheet_id()
            service_account_info = SheetDB.get_service_account_info()
            if not sheet_id or not service_account_info:
                return None

            credentials = Credentials.from_service_account_info(service_account_info, scopes=SheetDB.SCOPES)
            client = gspread.authorize(credentials)
            return client.open_by_key(sheet_id)
        except Exception as e:
            st.session_state["sheet_db_error"] = str(e)
            return None

    @staticmethod
    def worksheet(name: str, columns: list[str], default_rows: list[dict[str, Any]] | None = None):
        spreadsheet = SheetDB.spreadsheet()
        if not spreadsheet:
            return None
        try:
            ws = spreadsheet.worksheet(name)
        except Exception:
            ws = spreadsheet.add_worksheet(title=name, rows=500, cols=max(len(columns), 10))
            ws.append_row(columns)
            if default_rows:
                ws.append_rows([[SheetDB.to_sheet_value(row.get(col, "")) for col in columns] for row in default_rows])
            return ws

        # 若表頭空白或不是範本欄位，補齊第一列，不刪既有資料。
        try:
            header = ws.row_values(1)
            header = [h for h in header if str(h).strip()]
            if not header:
                SheetDB.update_values(ws, "A1", [columns])
            else:
                missing = [c for c in columns if c not in header]
                if missing:
                    fixed_header = header + missing
                    SheetDB.update_values(ws, "A1", [fixed_header])
        except Exception:
            pass
        return ws

    @staticmethod
    def update_values(ws, range_name: str, values: list[list[Any]]):
        """gspread v5/v6 相容更新，避免 Worksheet.update 參數順序錯誤。"""
        try:
            return ws.update(values=values, range_name=range_name)
        except TypeError:
            return ws.update(range_name, values)

    @staticmethod
    def get_records(ws, columns: list[str]) -> list[dict[str, Any]]:
        """安全讀取資料列：忽略 Google Sheet 範本後方空白欄，避免空白表頭造成錯誤。"""
        values = ws.get_all_values()
        if not values:
            return []
        header = [str(h).strip() for h in values[0]]
        index_map = {col: header.index(col) for col in columns if col in header}
        records = []
        for raw in values[1:]:
            row = {}
            has_data = False
            for col in columns:
                idx = index_map.get(col)
                val = raw[idx] if idx is not None and idx < len(raw) else ""
                row[col] = val
                if str(val).strip():
                    has_data = True
            if has_data:
                records.append(row)
        return records

    @staticmethod
    def to_sheet_value(value: Any) -> str:
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, (date, datetime)):
            return value.strftime("%Y-%m-%d") if isinstance(value, date) and not isinstance(value, datetime) else value.strftime("%Y-%m-%d %H:%M")
        if value is None:
            return ""
        return str(value)

    @staticmethod
    def normalize_records(records: list[dict[str, Any]], columns: list[str]) -> list[dict[str, Any]]:
        normalized = []
        for row in records:
            normalized.append({col: row.get(col, "") for col in columns})
        return normalized

    @staticmethod
    def load(name: str, columns: list[str], default_rows: list[dict[str, Any]] | None = None) -> list[dict[str, Any]] | None:
        ws = SheetDB.worksheet(name, columns, default_rows)
        if not ws:
            return None
        records = SheetDB.get_records(ws, columns)
        if not records and default_rows:
            SheetDB.save(name, columns, default_rows)
            records = default_rows
        return SheetDB.normalize_records(records, columns)

    @staticmethod
    def save(name: str, columns: list[str], records: list[dict[str, Any]]):
        ws = SheetDB.worksheet(name, columns)
        normalized = SheetDB.normalize_records(records, columns)
        if not ws:
            return False
        values = [columns]
        values.extend([[SheetDB.to_sheet_value(row.get(col, "")) for col in columns] for row in normalized])
        ws.clear()
        SheetDB.update_values(ws, "A1", values)
        return True


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def bool_text(value: Any, default: bool = True) -> str:
    if value in (True, "TRUE", "true", "1", 1, "是", "Y", "y"):
        return "TRUE"
    if value in (False, "FALSE", "false", "0", 0, "否", "N", "n"):
        return "FALSE"
    return "TRUE" if default else "FALSE"


def parse_date(value: Any, fallback: date | None = None) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if value in (None, ""):
        return fallback
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except Exception:
        return fallback


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except Exception:
        return default


def parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value or default))
    except Exception:
        return default


def parse_json_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    try:
        parsed = json.loads(str(value))
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return [x.strip() for x in str(value).split(",") if x.strip()]


# =========================================================
# 初始化
# =========================================================
class AppInitializer:
    @staticmethod
    def setup():
        st.session_state.setdefault("user_records_fallback", UserService.default_users())
        st.session_state.setdefault("announcements_fallback", [])
        st.session_state.setdefault("tasks_fallback", TaskService.default_tasks())
        st.session_state.setdefault("categories_fallback", CategoryService.default_categories())
        st.session_state.setdefault("tags_fallback", TagService.default_tags())
        st.session_state.setdefault("meetings_fallback", MeetingService.default_meetings())
        st.session_state.setdefault("approvals_fallback", ApprovalService.default_approvals())

        users = UserService.get_active_users()
        st.session_state.partners = [u.get("name", "") for u in users if u.get("name", "")]
        st.session_state.roles = {u.get("name", ""): parse_int(u.get("role_level", 0), 0) for u in users}

        st.session_state.categories = CategoryService.load_names()
        st.session_state.tags_list = TagService.load_names()
        st.session_state.tasks = TaskService.load_all()
        st.session_state.meetings = MeetingService.load_all()
        st.session_state.approvals = ApprovalService.load_all()

        st.session_state.setdefault("cal_year", date.today().year)
        st.session_state.setdefault("cal_month", date.today().month)
        st.session_state.setdefault("selected_date", date.today())



class UserService:
    WORKSHEET_NAME = "Users"
    DEFAULT_PASSWORD = "0000"
    COLUMNS = [
        "id", "name", "account", "password", "role", "role_level", "active",
        "must_change_password", "created_at", "updated_at", "last_login_at",
    ]

    @staticmethod
    def default_users():
        now = now_text()
        return [
            {"id": 1, "name": "闕老師", "account": "admin", "password": UserService.DEFAULT_PASSWORD, "role": "管理員", "role_level": 2, "active": "TRUE", "must_change_password": "TRUE", "created_at": now, "updated_at": now, "last_login_at": ""},
            {"id": 2, "name": "王大明", "account": "wang", "password": UserService.DEFAULT_PASSWORD, "role": "主管", "role_level": 1, "active": "TRUE", "must_change_password": "TRUE", "created_at": now, "updated_at": now, "last_login_at": ""},
            {"id": 3, "name": "陳小華", "account": "chen", "password": UserService.DEFAULT_PASSWORD, "role": "一般人員", "role_level": 0, "active": "TRUE", "must_change_password": "TRUE", "created_at": now, "updated_at": now, "last_login_at": ""},
            {"id": 4, "name": "林志玲", "account": "lin", "password": UserService.DEFAULT_PASSWORD, "role": "一般人員", "role_level": 0, "active": "TRUE", "must_change_password": "TRUE", "created_at": now, "updated_at": now, "last_login_at": ""},
        ]

    @staticmethod
    def using_google_sheet():
        return SheetDB.worksheet(UserService.WORKSHEET_NAME, UserService.COLUMNS, UserService.default_users()) is not None

    @staticmethod
    def load_all():
        records = SheetDB.load(UserService.WORKSHEET_NAME, UserService.COLUMNS, UserService.default_users())
        return records if records is not None else st.session_state.get("user_records_fallback", UserService.default_users())

    @staticmethod
    def save_all(records):
        records = SheetDB.normalize_records(records, UserService.COLUMNS)
        if not SheetDB.save(UserService.WORKSHEET_NAME, UserService.COLUMNS, records):
            st.session_state.user_records_fallback = records

    @staticmethod
    def get_active_users():
        return [u for u in UserService.load_all() if bool_text(u.get("active", "TRUE")) == "TRUE"]

    @staticmethod
    def get_by_account(account):
        target = str(account).strip().lower()
        for user in UserService.load_all():
            if str(user.get("account", "")).strip().lower() == target:
                return user
        return None

    @staticmethod
    def get_by_name(name):
        for user in UserService.load_all():
            if str(user.get("name", "")) == str(name):
                return user
        return None

    @staticmethod
    def authenticate(account, password):
        user = UserService.get_by_account(account)
        if not user or bool_text(user.get("active", "TRUE")) != "TRUE":
            return False, "帳號不存在或已停用。", None
        if str(user.get("password", "")) != str(password):
            return False, "密碼錯誤。", None

        records = UserService.load_all()
        now = now_text()
        for row in records:
            if str(row.get("account", "")).strip().lower() == str(account).strip().lower():
                row["last_login_at"] = now
                row["updated_at"] = now
        UserService.save_all(records)
        return True, "登入成功。", user

    @staticmethod
    def change_password(account, old_password, new_password, confirm_password, require_old=True):
        if len(str(new_password)) < 4:
            return False, "新密碼至少 4 碼。"
        if str(new_password) != str(confirm_password):
            return False, "兩次輸入的新密碼不一致。"

        records = UserService.load_all()
        target = str(account).strip().lower()
        for row in records:
            if str(row.get("account", "")).strip().lower() == target:
                if require_old and str(row.get("password", "")) != str(old_password):
                    return False, "原密碼錯誤。"
                row["password"] = str(new_password)
                row["must_change_password"] = "FALSE"
                row["updated_at"] = now_text()
                UserService.save_all(records)
                return True, "密碼已更新。"
        return False, "找不到帳號。"

    @staticmethod
    def upsert_user(name, account, role, role_level, active=True, reset_password=False, direct_password=""):
        records = UserService.load_all()
        now = now_text()
        target = str(account).strip().lower()
        next_id = max([parse_int(r.get("id", 0), 0) for r in records], default=0) + 1
        for row in records:
            if str(row.get("account", "")).strip().lower() == target:
                row["name"] = name.strip()
                row["role"] = role
                row["role_level"] = int(role_level)
                row["active"] = bool_text(active)
                if direct_password:
                    row["password"] = str(direct_password)
                    row["must_change_password"] = "TRUE"
                elif reset_password:
                    row["password"] = UserService.DEFAULT_PASSWORD
                    row["must_change_password"] = "TRUE"
                row["updated_at"] = now
                UserService.save_all(records)
                return "updated"

        records.append({
            "id": next_id,
            "name": name.strip(),
            "account": target,
            "password": str(direct_password) if direct_password else UserService.DEFAULT_PASSWORD,
            "role": role,
            "role_level": int(role_level),
            "active": bool_text(active),
            "must_change_password": "TRUE",
            "created_at": now,
            "updated_at": now,
            "last_login_at": "",
        })
        UserService.save_all(records)
        return "created"


class CategoryService:
    WORKSHEET_NAME = "Categories"
    COLUMNS = ["id", "name", "sort_order", "active", "created_at", "updated_at"]

    @staticmethod
    def default_categories():
        now = now_text()
        return [
            {"id": 1, "name": "待辦事項", "sort_order": 1, "active": "TRUE", "created_at": now, "updated_at": now},
            {"id": 2, "name": "進行中", "sort_order": 2, "active": "TRUE", "created_at": now, "updated_at": now},
            {"id": 3, "name": "已完成", "sort_order": 3, "active": "TRUE", "created_at": now, "updated_at": now},
        ]

    @staticmethod
    def load_all():
        records = SheetDB.load(CategoryService.WORKSHEET_NAME, CategoryService.COLUMNS, CategoryService.default_categories())
        return records if records is not None else st.session_state.get("categories_fallback", CategoryService.default_categories())

    @staticmethod
    def save_all(records):
        if not SheetDB.save(CategoryService.WORKSHEET_NAME, CategoryService.COLUMNS, records):
            st.session_state.categories_fallback = records

    @staticmethod
    def load_names():
        rows = [r for r in CategoryService.load_all() if bool_text(r.get("active", "TRUE")) == "TRUE"]
        rows = sorted(rows, key=lambda x: parse_int(x.get("sort_order", 0), 0))
        names = [r.get("name") for r in rows if r.get("name")]
        return names or ["待辦事項", "進行中", "已完成"]

    @staticmethod
    def add(name):
        records = CategoryService.load_all()
        if any(str(r.get("name", "")) == name for r in records):
            return False
        now = now_text()
        next_id = max([parse_int(r.get("id", 0), 0) for r in records], default=0) + 1
        records.append({"id": next_id, "name": name, "sort_order": next_id, "active": "TRUE", "created_at": now, "updated_at": now})
        CategoryService.save_all(records)
        return True


class TagService:
    WORKSHEET_NAME = "Tags"
    COLUMNS = ["id", "name", "active", "created_at", "updated_at"]

    @staticmethod
    def default_tags():
        now = now_text()
        return [
            {"id": 1, "name": "設計", "active": "TRUE", "created_at": now, "updated_at": now},
            {"id": 2, "name": "開發", "active": "TRUE", "created_at": now, "updated_at": now},
            {"id": 3, "name": "測試", "active": "TRUE", "created_at": now, "updated_at": now},
        ]

    @staticmethod
    def load_all():
        records = SheetDB.load(TagService.WORKSHEET_NAME, TagService.COLUMNS, TagService.default_tags())
        return records if records is not None else st.session_state.get("tags_fallback", TagService.default_tags())

    @staticmethod
    def load_names():
        return [r.get("name") for r in TagService.load_all() if r.get("name") and bool_text(r.get("active", "TRUE")) == "TRUE"] or ["設計", "開發", "測試"]


class TaskService:
    WORKSHEET_NAME = "Tasks"
    COLUMNS = [
        "id", "title", "category", "due", "assignees", "status", "progress", "hours_spent",
        "importance", "urgency", "tags", "notes", "depends_on", "history", "created_by", "created_account", "created_at", "updated_at",
    ]

    @staticmethod
    def default_tasks():
        now = now_text()
        return [
            {"id": 1, "title": "資料庫設計", "category": "進行中", "due": date.today() + timedelta(days=2), "assignees": ["王大明"], "status": "Active", "progress": 80, "hours_spent": 4.5, "importance": "高", "urgency": "高", "tags": "設計", "notes": "範例：所有任務會寫入本工作表", "depends_on": [], "history": [], "created_by": "系統", "created_account": "system", "created_at": now, "updated_at": now},
            {"id": 2, "title": "API 開發", "category": "待辦事項", "due": date.today() + timedelta(days=5), "assignees": ["陳小華"], "status": "Active", "progress": 0, "hours_spent": 0.0, "importance": "高", "urgency": "低", "tags": "開發", "notes": "", "depends_on": [], "history": [], "created_by": "系統", "created_account": "system", "created_at": now, "updated_at": now},
        ]

    @staticmethod
    def _from_sheet(row):
        row = {col: row.get(col, "") for col in TaskService.COLUMNS}
        row["id"] = parse_int(row.get("id"), 0)
        row["due"] = parse_date(row.get("due"), date.today())
        row["assignees"] = parse_json_list(row.get("assignees"))
        row["depends_on"] = [parse_int(x, 0) for x in parse_json_list(row.get("depends_on"))]
        row["history"] = parse_json_list(row.get("history"))
        row["progress"] = parse_int(row.get("progress"), 0)
        row["hours_spent"] = parse_float(row.get("hours_spent"), 0.0)
        row["status"] = row.get("status") or "Active"
        row["category"] = row.get("category") or "待辦事項"
        row["importance"] = row.get("importance") or "低"
        row["urgency"] = row.get("urgency") or "低"
        return row

    @staticmethod
    def _to_sheet(row):
        row = dict(row)
        row["due"] = parse_date(row.get("due"), date.today()).strftime("%Y-%m-%d")
        row["assignees"] = json.dumps(row.get("assignees", []), ensure_ascii=False)
        row["depends_on"] = json.dumps(row.get("depends_on", []), ensure_ascii=False)
        row["history"] = json.dumps(row.get("history", []), ensure_ascii=False)
        row["updated_at"] = row.get("updated_at") or now_text()
        return {col: row.get(col, "") for col in TaskService.COLUMNS}

    @staticmethod
    def load_all():
        records = SheetDB.load(TaskService.WORKSHEET_NAME, TaskService.COLUMNS, TaskService.default_tasks())
        rows = records if records is not None else st.session_state.get("tasks_fallback", TaskService.default_tasks())
        return [TaskService._from_sheet(r) for r in rows if r.get("title")]

    @staticmethod
    def save_all(records):
        rows = [TaskService._to_sheet(r) for r in records]
        if not SheetDB.save(TaskService.WORKSHEET_NAME, TaskService.COLUMNS, rows):
            st.session_state.tasks_fallback = records

    @staticmethod
    def add_task(task, author=None, account=None):
        records = TaskService.load_all()
        next_id = max([parse_int(t.get("id"), 0) for t in records], default=0) + 1
        now = now_text()
        task.update({
            "id": next_id,
            "created_by": author or task.get("created_by", ""),
            "created_account": account or task.get("created_account", ""),
            "created_at": now,
            "updated_at": now,
        })
        records.append(task)
        TaskService.save_all(records)
        st.session_state.tasks = records

    @staticmethod
    def get_filtered_tasks(f_assignees, f_tags, tasks=None):
        if tasks is None:
            tasks = st.session_state.tasks
        filtered = []
        for t in tasks:
            if t.get("status") != "Active":
                continue
            match_assignee = (not f_assignees) or any(a in f_assignees for a in t.get("assignees", []))
            match_tag = (not f_tags) or (t.get("tags") in f_tags)
            if match_assignee and match_tag:
                filtered.append(t)
        return filtered

    @staticmethod
    def is_task_locked(task):
        locked_by = [t["title"] for t in st.session_state.tasks if t.get("id") in task.get("depends_on", []) and t.get("category") != "已完成" and t.get("status") == "Active"]
        return len(locked_by) > 0, locked_by

    @staticmethod
    def calculate_team_capacity():
        active_tasks = [t for t in st.session_state.tasks if t.get("status") == "Active"]
        load_data = []
        for p in st.session_state.partners:
            active_count = len([t for t in active_tasks if p in t.get("assignees", []) and t.get("category") == "進行中"])
            ready_count = len([t for t in active_tasks if p in t.get("assignees", []) and t.get("category") == "待辦事項"])
            weight = (active_count * 1.0) + (ready_count * 0.3)
            load_data.append({"夥伴": p, "進行中(權重1.0)": active_count, "待辦(權重0.3)": ready_count, "總負載權重": round(weight, 1)})
        return pd.DataFrame(load_data)


class MeetingService:
    WORKSHEET_NAME = "Meetings"
    COLUMNS = ["id", "title", "time", "attendees", "link", "notes", "owner", "owner_account", "created_at", "updated_at"]

    @staticmethod
    def default_meetings():
        now = now_text()
        return [{"id": 1, "title": "週會範例", "time": date.today(), "attendees": ["闕老師"], "link": "", "notes": "這是一筆可刪除的範例會議", "owner": "闕老師", "owner_account": "admin", "created_at": now, "updated_at": now}]

    @staticmethod
    def _from_sheet(row):
        row = {col: row.get(col, "") for col in MeetingService.COLUMNS}
        row["id"] = parse_int(row.get("id"), 0)
        row["time"] = parse_date(row.get("time"), date.today())
        row["attendees"] = parse_json_list(row.get("attendees"))
        return row

    @staticmethod
    def _to_sheet(row):
        row = dict(row)
        row["time"] = parse_date(row.get("time"), date.today()).strftime("%Y-%m-%d")
        row["attendees"] = json.dumps(row.get("attendees", []), ensure_ascii=False)
        row["updated_at"] = row.get("updated_at") or now_text()
        return {col: row.get(col, "") for col in MeetingService.COLUMNS}

    @staticmethod
    def load_all():
        records = SheetDB.load(MeetingService.WORKSHEET_NAME, MeetingService.COLUMNS, MeetingService.default_meetings())
        rows = records if records is not None else st.session_state.get("meetings_fallback", MeetingService.default_meetings())
        return [MeetingService._from_sheet(r) for r in rows if r.get("title")]

    @staticmethod
    def save_all(records):
        rows = [MeetingService._to_sheet(r) for r in records]
        if not SheetDB.save(MeetingService.WORKSHEET_NAME, MeetingService.COLUMNS, rows):
            st.session_state.meetings_fallback = records

    @staticmethod
    def add_meeting(meeting, author=None, account=None):
        records = MeetingService.load_all()
        next_id = max([parse_int(m.get("id", 0), 0) for m in records], default=0) + 1
        now = now_text()
        meeting.update({
            "id": next_id,
            "owner": author or meeting.get("owner", ""),
            "owner_account": account or meeting.get("owner_account", ""),
            "created_at": now,
            "updated_at": now,
        })
        records.append(meeting)
        MeetingService.save_all(records)
        st.session_state.meetings = records

    @staticmethod
    def get_visible_meetings(target_date=None):
        # 取消全站登入後，會議清單預設全部可見。
        visible = list(st.session_state.meetings)
        if target_date:
            visible = [m for m in visible if m.get("time") == target_date]
        return visible


class ApprovalService:
    WORKSHEET_NAME = "Approvals"
    COLUMNS = ["id", "type", "content", "sender", "sender_account", "current_signer", "status", "history", "created_at", "updated_at"]

    @staticmethod
    def default_approvals():
        now = now_text()
        return [{"id": 1, "type": "請假單", "content": "範例簽呈，可刪除", "sender": "闕老師", "sender_account": "admin", "current_signer": "闕老師", "status": "簽核中", "history": ["[系統] 範例資料"], "created_at": now, "updated_at": now}]

    @staticmethod
    def _from_sheet(row):
        row = {col: row.get(col, "") for col in ApprovalService.COLUMNS}
        row["id"] = parse_int(row.get("id"), 0)
        row["history"] = parse_json_list(row.get("history"))
        return row

    @staticmethod
    def _to_sheet(row):
        row = dict(row)
        row["history"] = json.dumps(row.get("history", []), ensure_ascii=False)
        row["updated_at"] = row.get("updated_at") or now_text()
        return {col: row.get(col, "") for col in ApprovalService.COLUMNS}

    @staticmethod
    def load_all():
        records = SheetDB.load(ApprovalService.WORKSHEET_NAME, ApprovalService.COLUMNS, ApprovalService.default_approvals())
        rows = records if records is not None else st.session_state.get("approvals_fallback", ApprovalService.default_approvals())
        return [ApprovalService._from_sheet(r) for r in rows if r.get("type")]

    @staticmethod
    def save_all(records):
        rows = [ApprovalService._to_sheet(r) for r in records]
        if not SheetDB.save(ApprovalService.WORKSHEET_NAME, ApprovalService.COLUMNS, rows):
            st.session_state.approvals_fallback = records

    @staticmethod
    def add_approval(approval, author=None, account=None):
        records = ApprovalService.load_all()
        next_id = max([parse_int(a.get("id", 0), 0) for a in records], default=0) + 1
        now = now_text()
        approval.update({
            "id": next_id,
            "sender": author or approval.get("sender", ""),
            "sender_account": account or approval.get("sender_account", ""),
            "created_at": now,
            "updated_at": now,
        })
        records.append(approval)
        ApprovalService.save_all(records)
        st.session_state.approvals = records

    @staticmethod
    def process_action(approval, action, reason, signer_name, transfer_to=None):
        now_str = datetime.now().strftime("%m-%d %H:%M")
        if action == "同意":
            approval["status"] = "已同意"
            approval["history"].append(f"[{now_str}] {signer_name} 同意。意見: {reason}")
        elif action == "駁回":
            approval["status"] = "已駁回"
            approval["history"].append(f"[{now_str}] {signer_name} 駁回。意見: {reason}")
        elif action == "轉交":
            approval["current_signer"] = transfer_to
            approval["history"].append(f"[{now_str}] {signer_name} 轉交給 {transfer_to}。意見: {reason}")
        approval["updated_at"] = now_text()
        ApprovalService.save_all(st.session_state.approvals)


class AnnouncementService:
    WORKSHEET_NAME = "Announcements"
    COLUMNS = [
        "id", "title", "content", "level", "author", "author_account", "created_at", "expires_at",
        "pinned", "active", "attachment_name", "attachment_type", "attachment_base64", "seen_by",
    ]

    @staticmethod
    def is_admin(user=None):
        return st.session_state.roles.get(user or "", 0) >= 2

    @staticmethod
    def using_google_sheet():
        return SheetDB.worksheet(AnnouncementService.WORKSHEET_NAME, AnnouncementService.COLUMNS) is not None

    @staticmethod
    def load_all():
        records = SheetDB.load(AnnouncementService.WORKSHEET_NAME, AnnouncementService.COLUMNS, [])
        return records if records is not None else st.session_state.get("announcements_fallback", [])

    @staticmethod
    def save_all(records):
        records = SheetDB.normalize_records(records, AnnouncementService.COLUMNS)
        if not SheetDB.save(AnnouncementService.WORKSHEET_NAME, AnnouncementService.COLUMNS, records):
            st.session_state.announcements_fallback = records

    @staticmethod
    def get_active():
        today = date.today()
        active = []
        for ann in AnnouncementService.load_all():
            if bool_text(ann.get("active", "TRUE")) == "FALSE":
                continue
            expires_at = parse_date(ann.get("expires_at", ""), None)
            if expires_at and expires_at < today:
                continue
            active.append(ann)
        return sorted(active, key=lambda a: (bool_text(a.get("pinned", "FALSE"), False) != "TRUE", -parse_int(a.get("id", 0), 0)))

    @staticmethod
    def create(title, content, level, expires_at, pinned, attachment, author=None, account=None):
        records = AnnouncementService.load_all()
        next_id = max([parse_int(r.get("id", 0), 0) for r in records], default=0) + 1
        attachment_name = ""
        attachment_type = ""
        attachment_base64 = ""
        if attachment:
            data = attachment.getvalue()
            attachment_name = attachment.name
            attachment_type = attachment.type or "application/octet-stream"
            attachment_base64 = base64.b64encode(data).decode("utf-8")
        records.append({
            "id": next_id, "title": title.strip(), "content": content.strip(), "level": level,
            "author": author or "未指定", "author_account": account or "", "created_at": now_text(),
            "expires_at": expires_at.strftime("%Y-%m-%d") if expires_at else "",
            "pinned": bool_text(pinned), "active": "TRUE", "attachment_name": attachment_name,
            "attachment_type": attachment_type, "attachment_base64": attachment_base64, "seen_by": "",
        })
        AnnouncementService.save_all(records)

    @staticmethod
    def update_flag(announcement_id, field, value):
        records = AnnouncementService.load_all()
        for row in records:
            if parse_int(row.get("id", 0), 0) == int(announcement_id):
                row[field] = value
        AnnouncementService.save_all(records)

    @staticmethod
    def mark_seen(announcement_id, user):
        records = AnnouncementService.load_all()
        changed = False
        for row in records:
            if parse_int(row.get("id", 0), 0) == int(announcement_id):
                seen = [x.strip() for x in str(row.get("seen_by", "")).split(",") if x.strip()]
                if user not in seen:
                    seen.append(user)
                    row["seen_by"] = ",".join(seen)
                    changed = True
        if changed:
            AnnouncementService.save_all(records)

    @staticmethod
    def unread_count(user):
        count = 0
        for ann in AnnouncementService.get_active():
            seen = [x.strip() for x in str(ann.get("seen_by", "")).split(",") if x.strip()]
            if user not in seen:
                count += 1
        return count


class ViewComponents:
    @staticmethod
    def require_login():
        """保留舊頁面呼叫名稱，但不再強制全站登入。"""
        ViewComponents.render_public_sidebar()

    @staticmethod
    def render_filters():
        with st.expander("🔍 進階多維度篩選器", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                f_a = st.multiselect("篩選指派對象", st.session_state.partners)
            with c2:
                f_t = st.multiselect("篩選標籤", st.session_state.tags_list)
            return f_a, f_t

    @staticmethod
    def render_login_gate():
        """舊版相容：不再顯示登入牆。"""
        return True

    @staticmethod
    def render_user_sidebar():
        ViewComponents.render_public_sidebar()

    @staticmethod
    def render_public_sidebar():
        st.sidebar.title("導覽控制")
        st.sidebar.info("目前版本v1.04(新增/發布資料時才驗證工號與密碼。)")
        if not UserService.using_google_sheet():
            st.sidebar.warning("未偵測到 Google Sheet，資料會暫存在本次執行階段。")
            if st.session_state.get("sheet_db_error"):
                st.sidebar.caption(f"連線訊息：{st.session_state.sheet_db_error}")

        with st.sidebar.expander("👥 人員資料提醒", expanded=False):
            st.caption("任務、會議、簽核與公告發布都會檢查 Users 工作表中的工號與密碼。")
            st.caption("Users 工作表建議保留欄位：name、account、password、role、role_level、active。")

    @staticmethod
    def get_active_announcement_count():
        return len(AnnouncementService.get_active())

    @staticmethod
    def _validate_publisher(account, password):
        ok, msg, user = UserService.authenticate(account, password)
        if not ok:
            return False, msg, None
        return True, "發布人驗證成功。", user

    @staticmethod
    def render_announcement_board():
        level_icon = {"一般": "📌", "重要": "⚠️", "緊急": "🚨", "維護": "🛠️"}
        level_label = {"一般": "一般公告", "重要": "重要公告", "緊急": "緊急公告", "維護": "維護公告"}
        user = "訪客"
        announcements = AnnouncementService.get_active()
        unread_count = AnnouncementService.unread_count(user)
        pinned_titles = [a.get("title", "") for a in announcements if bool_text(a.get("pinned", "FALSE"), False) == "TRUE"]
        if pinned_titles:
            marquee_text = "　｜　".join([f"📢 {title}" for title in pinned_titles])
            st.markdown(f"""
                <div style="overflow:hidden; white-space:nowrap; border:1px solid #e5e7eb; border-radius:10px; padding:10px; margin-bottom:12px;">
                    <marquee behavior="scroll" direction="left" scrollamount="5">{marquee_text}</marquee>
                </div>
                """, unsafe_allow_html=True)

        title_col, status_col = st.columns([5, 2])
        with title_col:
            st.subheader("📢 鋒霈 工程部布告欄")
        with status_col:
            if unread_count > 0:
                st.warning(f"🔔 你有 {unread_count} 則新公告")
                try:
                    st.toast(f"你有 {unread_count} 則新公告", icon="🔔")
                except Exception:
                    pass
            else:
                st.success("✅ 無未讀公告")

        if not AnnouncementService.using_google_sheet():
            st.info("目前未偵測到 Google Sheet 設定，公告會暫存在本次執行階段。部署時請設定 Streamlit Secrets。")

        with st.expander("📣 發布公告（需輸入發布人工號與密碼）", expanded=False):
            with st.form("enterprise_announcement_form", clear_on_submit=True):
                c0a, c0b = st.columns(2)
                with c0a:
                    publisher_account = st.text_input("發布人工號 / 帳號")
                with c0b:
                    publisher_password = st.text_input("發布人密碼", type="password")

                title = st.text_input("公告標題")
                content = st.text_area("公告內容", height=140)
                c1, c2, c3 = st.columns(3)
                with c1:
                    level = st.selectbox("公告等級", ["一般", "重要", "緊急", "維護"])
                with c2:
                    expires_at = st.date_input("到期日", value=date.today() + timedelta(days=30))
                with c3:
                    pinned = st.checkbox("跑馬燈置頂", value=False)
                attachment = st.file_uploader("附件（圖片 / PDF，建議 5MB 以下）", type=["png", "jpg", "jpeg", "pdf"])
                submitted = st.form_submit_button("發布公告", use_container_width=True)
                if submitted:
                    if not publisher_account.strip() or not publisher_password:
                        st.warning("請輸入發布人的工號與密碼。")
                    elif not title.strip() or not content.strip():
                        st.warning("請輸入公告標題與內容。")
                    elif attachment and attachment.size > 5 * 1024 * 1024:
                        st.error("附件超過 5MB，請壓縮後再上傳。")
                    else:
                        ok, msg, publisher = ViewComponents._validate_publisher(publisher_account, publisher_password)
                        if not ok:
                            st.error(msg)
                        else:
                            author = publisher.get("name") or publisher.get("account") or publisher_account
                            AnnouncementService.create(title, content, level, expires_at, pinned, attachment, author=author, account=publisher.get("account", publisher_account))
                            st.success(f"公告已發布並寫入布告欄。發布人：{author}")
                            st.rerun()

        if not announcements:
            st.info("目前沒有有效公告。")
            return

        for ann in announcements:
            ann_id = parse_int(ann.get("id", 0), 0)
            icon = level_icon.get(ann.get("level", "一般"), "📌")
            seen = [x.strip() for x in str(ann.get("seen_by", "")).split(",") if x.strip()]
            is_unread = user not in seen
            pinned_text = "｜📢 跑馬燈置頂" if bool_text(ann.get("pinned", "FALSE"), False) == "TRUE" else ""
            unread_text = "｜🔔 新公告" if is_unread else ""
            with st.container(border=True):
                st.markdown(f"### {icon} {ann.get('title', '')}")
                st.caption(f"{level_label.get(ann.get('level', '一般'), '一般公告')}{pinned_text}{unread_text}｜發布人：{ann.get('author', '未知')}｜發布時間：{ann.get('created_at', '-')}｜到期日：{ann.get('expires_at', '未設定')}")
                st.write(ann.get("content", ""))
                attachment_name = ann.get("attachment_name", "")
                attachment_type = ann.get("attachment_type", "")
                attachment_base64 = ann.get("attachment_base64", "")
                if attachment_name and attachment_base64:
                    try:
                        raw = base64.b64decode(attachment_base64)
                        if str(attachment_type).startswith("image/"):
                            st.image(raw, caption=attachment_name, use_container_width=False)
                        st.download_button(label=f"📎 下載附件：{attachment_name}", data=raw, file_name=attachment_name, mime=attachment_type or "application/octet-stream", key=f"download_ann_{ann_id}")
                    except Exception:
                        st.warning("附件資料讀取失敗，請由管理員重新上傳。")
                if is_unread:
                    if st.button("標記已讀", key=f"seen_ann_{ann_id}"):
                        AnnouncementService.mark_seen(ann_id, user)
                        st.rerun()

                with st.expander("公告管理（需管理員工號與密碼）", expanded=False):
                    admin_account = st.text_input("管理員工號 / 帳號", key=f"admin_acc_{ann_id}")
                    admin_password = st.text_input("管理員密碼", type="password", key=f"admin_pwd_{ann_id}")
                    b1, b2, b3, _ = st.columns([1.2, 1.2, 1.2, 5])
                    def admin_ok():
                        ok, msg, admin = UserService.authenticate(admin_account, admin_password)
                        if not ok:
                            st.error(msg)
                            return False
                        if parse_int(admin.get("role_level", 0), 0) < 2:
                            st.error("此帳號不是管理員，無法管理公告。")
                            return False
                        return True
                    with b1:
                        if st.button("置頂/取消", key=f"pin_ann_{ann_id}") and admin_ok():
                            new_value = "FALSE" if bool_text(ann.get("pinned", "FALSE"), False) == "TRUE" else "TRUE"
                            AnnouncementService.update_flag(ann_id, "pinned", new_value)
                            st.rerun()
                    with b2:
                        if st.button("立即下架", key=f"off_ann_{ann_id}") and admin_ok():
                            AnnouncementService.update_flag(ann_id, "active", "FALSE")
                            st.rerun()
                    with b3:
                        if st.button("清除已讀", key=f"clear_seen_ann_{ann_id}") and admin_ok():
                            AnnouncementService.update_flag(ann_id, "seen_by", "")
                            st.rerun()


class StreamFlowEngine:
    @staticmethod
    def add_log(task, message, author="系統"):
        if "history" not in task:
            task["history"] = []
        task["history"].append(f"[{datetime.now().strftime('%m-%d %H:%M')}] {author} {message}")
        task["updated_at"] = now_text()
