import base64
import json
from datetime import date, datetime, timedelta
from typing import Any
from pathlib import Path

import pandas as pd
import streamlit as st

from services.sheet_db import SheetDB
from config.departments import DEPARTMENTS, INDEPENDENT_DEPARTMENT


def current_department() -> str:
    return st.session_state.get("current_department", DEPARTMENTS[0])


def record_department(row: dict[str, Any]) -> str:
    """舊資料沒有 department 時歸入第一課，確保升級後仍可看到。"""
    account = str(row.get("account", "")).strip().lower()
    role = str(row.get("role", "")).strip()
    role_level = parse_int(row.get("role_level", 0), 0) if "parse_int" in globals() else 0
    if account in {"developer", "dev", "admin"} or role == "開發者" or role_level >= 9:
        return INDEPENDENT_DEPARTMENT
    return str(row.get("department") or DEPARTMENTS[0]).strip()

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
    VERSION = "V5.5.3 Independent Developer Account"

    @staticmethod
    def load_enterprise_theme():
        """Inject one shared enterprise theme across all Streamlit pages.

        Streamlit reruns rebuild the DOM, so the CSS must be injected on every run.
        """
        root = Path(__file__).resolve().parent
        if root.name == "services":
            root = root.parent
        css_path = root / "assets" / "enterprise_theme_v1.css"
        try:
            css = css_path.read_text(encoding="utf-8")
            st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
        except Exception:
            # Theme loading must never block the business system.
            pass

    @staticmethod
    def setup(load_tasks: bool = True, load_meetings: bool = False, load_approvals: bool = False):
        """V3.4 Turbo 初始化。

        原本每次進入任一頁面都讀 Users / Categories / Tags / Tasks / Meetings / Approvals。
        這版改成：
        - 首頁與任務頁只載入必要資料。
        - Meetings / Approvals 採 Lazy Load，進入該頁面才讀。
        - 已載入資料會放在 session_state，Google Sheet 讀取由 SheetDB 分層快取控管。
        """
        st.session_state.setdefault("app_version", AppInitializer.VERSION)
        AppInitializer.load_enterprise_theme()
        st.session_state.setdefault("user_records_fallback", UserService.default_users())
        st.session_state.setdefault("announcements_fallback", [])
        st.session_state.setdefault("tasks_fallback", TaskService.default_tasks())
        st.session_state.setdefault("categories_fallback", CategoryService.default_categories())
        st.session_state.setdefault("tags_fallback", TagService.default_tags())
        st.session_state.setdefault("meetings_fallback", MeetingService.default_meetings())
        st.session_state.setdefault("approvals_fallback", ApprovalService.default_approvals())
        st.session_state.setdefault("tasks", st.session_state.get("tasks_fallback", []))
        st.session_state.setdefault("meetings", st.session_state.get("meetings_fallback", []))
        st.session_state.setdefault("approvals", st.session_state.get("approvals_fallback", []))

        # One batch request replaces 3-4 serial Google Sheet reads on first page load.
        prefetch_specs = [
            (UserService.WORKSHEET_NAME, UserService.COLUMNS, UserService.default_users()),
            (CategoryService.WORKSHEET_NAME, CategoryService.COLUMNS, CategoryService.default_categories()),
            (TagService.WORKSHEET_NAME, TagService.COLUMNS, TagService.default_tags()),
        ]
        if load_tasks:
            prefetch_specs.append((TaskService.WORKSHEET_NAME, TaskService.COLUMNS, TaskService.default_tasks()))
        if load_meetings:
            prefetch_specs.append((MeetingService.WORKSHEET_NAME, MeetingService.COLUMNS, MeetingService.default_meetings()))
        if load_approvals:
            prefetch_specs.append((ApprovalService.WORKSHEET_NAME, ApprovalService.COLUMNS, ApprovalService.default_approvals()))
        SheetDB.prefetch(prefetch_specs)

        users = UserService.get_active_users()
        available_departments = UserService.get_departments() or DEPARTMENTS
        if st.session_state.get("current_department") not in available_departments:
            st.session_state.current_department = available_departments[0]
        st.sidebar.selectbox(
            "🏢 選擇部門",
            available_departments,
            key="current_department",
            help="各功能、任務、人員、會議與簽核資料會依此課別獨立顯示。",
        )
        users = [u for u in users if UserService.has_department(u, current_department())]
        partners = []
        seen = set()
        for user in users:
            name = str(user.get("name", "")).strip()
            if name and name not in seen:
                seen.add(name)
                partners.append(name)

        st.session_state.partners = sorted(partners)
        st.session_state.roles = {u.get("name", ""): UserService.effective_role_level(u) for u in users}
        st.session_state.categories = CategoryService.load_names()
        st.session_state.tags_list = TagService.load_names()

        if load_tasks:
            st.session_state.tasks = TaskService.load_by_department(current_department())
        if load_meetings:
            st.session_state.meetings = MeetingService.load_by_department(current_department())
        if load_approvals:
            st.session_state.approvals = ApprovalService.load_by_department(current_department())

        st.session_state.setdefault("cal_year", date.today().year)
        st.session_state.setdefault("cal_month", date.today().month)
        st.session_state.setdefault("selected_date", date.today())
        st.session_state.setdefault("current_user", "訪客")



class UserService:
    WORKSHEET_NAME = "Users"
    DEFAULT_PASSWORD = "0000"
    COLUMNS = [
        "id", "name", "account", "password", "role", "role_level", "active",
        "department", "assignments", "must_change_password", "created_at", "updated_at", "last_login_at",
    ]

    @staticmethod
    def default_users():
        now = now_text()
        return [
            {"id": 1, "name": "開發者", "account": "developer", "password": UserService.DEFAULT_PASSWORD, "role": "開發者", "role_level": 9, "active": "TRUE", "department": INDEPENDENT_DEPARTMENT, "assignments": "[]", "must_change_password": "TRUE", "created_at": now, "updated_at": now, "last_login_at": ""},
        ]

    @staticmethod
    def using_google_sheet():
        return SheetDB.spreadsheet() is not None

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
    def get_assignments(user: dict | None) -> list[dict]:
        """回傳主要職務＋兼任職務，並移除重複組合。"""
        if not user:
            return []
        primary = {
            "department": record_department(user),
            "role": str(user.get("role") or "助理工程師"),
            "role_level": parse_int(user.get("role_level", 0), 0),
            "primary": True,
        }
        rows = [primary]
        for item in parse_json_list(user.get("assignments")):
            if not isinstance(item, dict):
                continue
            department = str(item.get("department") or "").strip()
            role = str(item.get("role") or "").strip()
            if not department or not role:
                continue
            rows.append({
                "department": department,
                "role": role,
                "role_level": parse_int(item.get("role_level", 0), 0),
                "primary": False,
            })
        unique = []
        seen = set()
        for item in rows:
            key = (item["department"], item["role"])
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique

    @staticmethod
    def effective_role_level(user: dict | None) -> int:
        return max([parse_int(item.get("role_level", 0), 0) for item in UserService.get_assignments(user)], default=0)

    @staticmethod
    def has_department(user: dict | None, department: str) -> bool:
        if record_department(user or {}) == INDEPENDENT_DEPARTMENT:
            return False
        return any(item.get("department") == department for item in UserService.get_assignments(user))

    @staticmethod
    def roles_in_department(user: dict | None, department: str) -> list[str]:
        return [item.get("role", "") for item in UserService.get_assignments(user) if item.get("department") == department]

    @staticmethod
    def get_partner_names() -> list[str]:
        """Return active user display names from the Users Google Sheet.

        This is the single source for all assignee / attendee / signer dropdowns.
        Duplicate or blank names are removed, and the result is sorted for stable UI.
        """
        names = []
        seen = set()
        for user in UserService.get_active_users():
            if not UserService.has_department(user, current_department()):
                continue
            name = str(user.get("name", "")).strip()
            if name and name not in seen:
                seen.add(name)
                names.append(name)
        return sorted(names)

    @staticmethod
    def get_all_partner_names(preferred_department: str | None = None) -> list[str]:
        """回傳所有啟用人員，並將指定部門的人員優先排列。"""
        preferred_department = preferred_department or current_department()
        preferred = []
        others = []
        seen = set()
        for user in UserService.get_active_users():
            name = str(user.get("name", "")).strip()
            if not name or name in seen:
                continue
            seen.add(name)
            target = preferred if UserService.has_department(user, preferred_department) else others
            target.append(name)
        return sorted(preferred) + sorted(others)

    @staticmethod
    def get_partner_names_by_department(department: str) -> list[str]:
        """回傳主要或兼任指定部門的所有啟用人員。"""
        names = {
            str(user.get("name", "")).strip()
            for user in UserService.get_active_users()
            if UserService.has_department(user, department)
        }
        return sorted(name for name in names if name)

    @staticmethod
    def get_departments() -> list[str]:
        configured = {record_department(u) for u in UserService.load_all() if record_department(u)}
        return [d for d in DEPARTMENTS if d in configured] + [d for d in DEPARTMENTS if d not in configured]

    @staticmethod
    def get_users_by_department(department: str, active_only: bool = True) -> list[dict]:
        rows = UserService.get_active_users() if active_only else UserService.load_all()
        return [u for u in rows if UserService.has_department(u, department)]

    @staticmethod
    def is_developer_user(user: dict[str, Any] | None) -> bool:
        """開發者判定規則。

        請在 Google Sheet 的 Users 工作表建立一筆開發者人員：
        - role 填「開發者」或 developer
        - 或 account 填 developer / dev
        - 或 role_level 設為 9 以上
        - active 必須為 TRUE
        """
        if not user:
            return False
        if bool_text(user.get("active", "TRUE")) != "TRUE":
            return False
        account = str(user.get("account", "")).strip().lower()
        role = str(user.get("role", "")).strip().lower()
        role_level = UserService.effective_role_level(user)
        return (
            account in {"developer", "dev"}
            or "開發" in role
            or "developer" in role
            or "dev" == role
            or role_level >= 9
        )

    @staticmethod
    def verify_developer_password(password: str) -> tuple[bool, str]:
        """只用密碼開啟首頁 Google Sheet 診斷，不做全站登入。"""
        if not str(password or "").strip():
            return False, "請輸入開發者密碼。"
        developers = [u for u in UserService.get_active_users() if UserService.is_developer_user(u)]
        if not developers:
            return False, "Users 工作表尚未建立開發者帳號。請將開發者的 role 設為「開發者」或 role_level 設為 9 以上。"
        for user in developers:
            if str(user.get("password", "")) == str(password):
                return True, "開發者驗證成功。"
        return False, "開發者密碼錯誤。"

    @staticmethod
    def verify_management_credentials(account: str, password: str, minimum_level: int = 6):
        ok, msg, user = UserService.authenticate(account, password)
        if not ok:
            return False, msg, None
        level = UserService.effective_role_level(user)
        if level < minimum_level:
            return False, f"權限不足：人員管理需要權限 {minimum_level} 以上。", None
        return True, "管理權限驗證成功。", user

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
    def upsert_user(name, account, role, role_level, active=True, reset_password=False, direct_password="", department=None, assignments=None):
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
                row["department"] = department or record_department(row)
                if assignments is not None:
                    row["assignments"] = json.dumps(assignments, ensure_ascii=False)
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
            "department": department or current_department(),
            "assignments": json.dumps(assignments or [], ensure_ascii=False),
            "must_change_password": "TRUE",
            "created_at": now,
            "updated_at": now,
            "last_login_at": "",
        })
        UserService.save_all(records)
        return "created"

    @staticmethod
    def delete_user(account: str) -> tuple[bool, str]:
        target = str(account).strip().lower()
        records = UserService.load_all()
        victim = next((r for r in records if str(r.get("account", "")).strip().lower() == target), None)
        if not victim:
            return False, "找不到指定人員。"
        if UserService.is_developer_user(victim):
            developers = [r for r in records if UserService.is_developer_user(r)]
            if len(developers) <= 1:
                return False, "不可刪除系統中最後一位開發者。"
        UserService.save_all([r for r in records if r is not victim])
        return True, "人員已刪除。"


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
        "department", "importance", "urgency", "tags", "notes", "depends_on", "history", "created_by", "created_account", "created_at", "updated_at",
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
    def load_by_department(department):
        return [r for r in TaskService.load_all() if record_department(r) == department]

    @staticmethod
    def save_all(records):
        rows = [TaskService._to_sheet(r) for r in records]
        if not SheetDB.save(TaskService.WORKSHEET_NAME, TaskService.COLUMNS, rows):
            st.session_state.tasks_fallback = records

    @staticmethod
    def add_task(task, author=None, account=None):
        records = TaskService.load_all()
        next_id = max([parse_int(t.get("id", 0), 0) for t in records], default=0) + 1
        now = now_text()
        task.update({
            "id": next_id,
            "created_by": author or task.get("created_by", ""),
            "created_account": account or task.get("created_account", ""),
            "created_at": now,
            "updated_at": now,
            "department": task.get("department") or current_department(),
        })
        row = TaskService._to_sheet(task)
        ok = SheetDB.append(TaskService.WORKSHEET_NAME, TaskService.COLUMNS, row)
        if not ok:
            records.append(task)
            st.session_state.tasks_fallback = records
            raise RuntimeError(st.session_state.get("sheet_db_error", "Google Sheet 任務寫入失敗"))
        records.append(task)
        st.session_state.tasks = records
        return True

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
        for p in UserService.get_partner_names():
            active_count = len([t for t in active_tasks if p in t.get("assignees", []) and t.get("category") == "進行中"])
            ready_count = len([t for t in active_tasks if p in t.get("assignees", []) and t.get("category") == "待辦事項"])
            weight = (active_count * 1.0) + (ready_count * 0.3)
            load_data.append({"夥伴": p, "進行中(權重1.0)": active_count, "待辦(權重0.3)": ready_count, "總負載權重": round(weight, 1)})
        return pd.DataFrame(load_data)


class MeetingService:
    WORKSHEET_NAME = "Meetings"
    COLUMNS = ["id", "department", "title", "time", "attendees", "link", "notes", "owner", "owner_account", "created_at", "updated_at"]

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
    def load_by_department(department):
        return [r for r in MeetingService.load_all() if record_department(r) == department]

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
            "department": meeting.get("department") or current_department(),
        })
        row = MeetingService._to_sheet(meeting)
        ok = SheetDB.append(MeetingService.WORKSHEET_NAME, MeetingService.COLUMNS, row)
        if not ok:
            records.append(meeting)
            st.session_state.meetings_fallback = records
            raise RuntimeError(st.session_state.get("sheet_db_error", "Google Sheet 會議寫入失敗"))
        records.append(meeting)
        st.session_state.meetings = records
        return True

    @staticmethod
    def get_visible_meetings(target_date=None):
        # 取消全站登入後，會議清單預設全部可見。
        visible = list(st.session_state.meetings)
        if target_date:
            visible = [m for m in visible if m.get("time") == target_date]
        return visible


class ApprovalService:
    WORKSHEET_NAME = "Approvals"
    COLUMNS = ["id", "department", "type", "content", "sender", "sender_account", "current_signer", "status", "history", "created_at", "updated_at"]

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
    def load_by_department(department):
        return [r for r in ApprovalService.load_all() if record_department(r) == department]

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
            "department": approval.get("department") or current_department(),
        })
        row = ApprovalService._to_sheet(approval)
        ok = SheetDB.append(ApprovalService.WORKSHEET_NAME, ApprovalService.COLUMNS, row)
        if not ok:
            records.append(approval)
            st.session_state.approvals_fallback = records
            raise RuntimeError(st.session_state.get("sheet_db_error", "Google Sheet 簽核寫入失敗"))
        records.append(approval)
        st.session_state.approvals = records
        return True

    @staticmethod
    def process_action(approval, action, reason="", signer_name=None, transfer_to=None):
        """處理簽核動作。

        相容舊頁面呼叫：ApprovalService.process_action(a, act, rsn, trans)
        舊呼叫的第 4 參數其實是轉交對象，因此這裡自動判斷。
        """
        if action == "轉交" and transfer_to is None and signer_name not in (None, ""):
            transfer_to = signer_name
            signer_name = st.session_state.get("current_user", "系統")
        signer_name = signer_name or st.session_state.get("current_user", "系統")

        now_str = datetime.now().strftime("%m-%d %H:%M")
        approval.setdefault("history", [])
        if action == "同意":
            approval["status"] = "已同意"
            approval["history"].append(f"[{now_str}] {signer_name} 同意。意見: {reason}")
        elif action == "駁回":
            approval["status"] = "已駁回"
            approval["history"].append(f"[{now_str}] {signer_name} 駁回。意見: {reason}")
        elif action == "轉交":
            approval["current_signer"] = transfer_to or approval.get("current_signer", "")
            approval["history"].append(f"[{now_str}] {signer_name} 轉交給 {approval.get('current_signer', '')}。意見: {reason}")
        approval["updated_at"] = now_text()
        all_records = ApprovalService.load_all()
        for index, row in enumerate(all_records):
            if parse_int(row.get("id"), 0) == parse_int(approval.get("id"), 0):
                all_records[index] = approval
                break
        ApprovalService.save_all(all_records)


class AnnouncementService:
    WORKSHEET_NAME = "Announcements"
    COLUMNS = [
        "id", "department", "title", "content", "level", "author", "author_account", "created_at", "expires_at",
        "pinned", "active", "attachment_name", "attachment_type", "attachment_base64", "seen_by",
    ]

    @staticmethod
    def is_admin(user=None):
        return st.session_state.roles.get(user or "", 0) >= 6

    @staticmethod
    def using_google_sheet():
        return SheetDB.spreadsheet() is not None

    @staticmethod
    def load_all():
        records = SheetDB.load(AnnouncementService.WORKSHEET_NAME, AnnouncementService.COLUMNS, [])
        return records if records is not None else st.session_state.get("announcements_fallback", [])

    @staticmethod
    def save_all(records):
        records = SheetDB.normalize_records(records, AnnouncementService.COLUMNS)
        ok = SheetDB.save(
            AnnouncementService.WORKSHEET_NAME,
            AnnouncementService.COLUMNS,
            records,
        )

        if not ok:
            st.session_state.announcements_fallback = records

        return ok

    @staticmethod
    def get_active():
        today = date.today()
        active = []
        for ann in AnnouncementService.load_all():
            if record_department(ann) != current_department():
                continue
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

        row = {
            "id": next_id,
            "department": current_department(),
            "title": title.strip(),
            "content": content.strip(),
            "level": level,
            "author": author or "未指定",
            "author_account": account or "",
            "created_at": now_text(),
            "expires_at": expires_at.strftime("%Y-%m-%d") if expires_at else "",
            "pinned": bool_text(pinned),
            "active": "TRUE",
            "attachment_name": attachment_name,
            "attachment_type": attachment_type,
            "attachment_base64": attachment_base64,
            "seen_by": "",
        }

        ok = SheetDB.append(AnnouncementService.WORKSHEET_NAME, AnnouncementService.COLUMNS, row)
        if not ok:
            fallback = st.session_state.get("announcements_fallback", records)
            fallback.append(row)
            st.session_state.announcements_fallback = fallback
            raise RuntimeError(
                st.session_state.get(
                    "sheet_db_error",
                    "Google Sheet 寫入失敗，公告只暫存在本次執行階段。",
                )
            )

        return True

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
