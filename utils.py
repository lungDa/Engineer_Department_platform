import base64
import os
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st


class AppInitializer:
    @staticmethod
    def setup():
        # 基本資料只初始化一次，避免重複覆蓋登入狀態與使用者資料。
        if "tasks" not in st.session_state:
            st.session_state.tasks = [
                {"id": 1, "title": "資料庫設計", "category": "進行中", "due": date.today() + timedelta(days=2), "assignees": ["王大明"], "status": "Active", "progress": 80, "hours_spent": 4.5, "importance": "高", "urgency": "高", "history": []},
                {"id": 2, "title": "API 開發", "category": "待辦事項", "due": date.today() + timedelta(days=5), "assignees": ["陳小華"], "status": "Active", "progress": 0, "hours_spent": 0.0, "importance": "高", "urgency": "低", "history": []},
            ]
            st.session_state.categories = ["待辦事項", "進行中", "已完成"]
            st.session_state.meetings = []
            st.session_state.approvals = []
            st.session_state.tags_list = ["設計", "開發", "測試"]
            st.session_state.cal_year = date.today().year
            st.session_state.cal_month = date.today().month
            st.session_state.selected_date = date.today()
            st.session_state.announcements_fallback = []

        # 登入與人員資料狀態
        st.session_state.setdefault("auth_user", None)
        st.session_state.setdefault("current_user", "")
        st.session_state.setdefault("user_records_fallback", UserService.default_users())

        users = UserService.get_active_users()
        st.session_state.partners = [u.get("name", "") for u in users if u.get("name", "")]
        st.session_state.roles = {u.get("name", ""): int(float(u.get("role_level", 0) or 0)) for u in users}

        if st.session_state.auth_user:
            st.session_state.current_user = st.session_state.auth_user
        elif not st.session_state.current_user and st.session_state.partners:
            st.session_state.current_user = st.session_state.partners[0]


class UserService:
    """人員帳號服務：使用 Google Sheet 的 Users 工作表保存人員與明碼密碼。"""

    WORKSHEET_NAME = "Users"
    DEFAULT_PASSWORD = "0000"
    COLUMNS = [
        "id", "name", "account", "password", "role", "role_level", "active",
        "must_change_password", "created_at", "updated_at", "last_login_at",
    ]

    @staticmethod
    def default_users():
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        return [
            {"id": 1, "name": "開發者", "account": "admin", "password": UserService.DEFAULT_PASSWORD, "role": "管理員", "role_level": 2, "active": "TRUE", "must_change_password": "TRUE", "created_at": now, "updated_at": now, "last_login_at": ""},
            {"id": 2, "name": "廖郁仁", "account": "243", "password": UserService.DEFAULT_PASSWORD, "role": "主管", "role_level": 2, "active": "TRUE", "must_change_password": "TRUE", "created_at": now, "updated_at": now, "last_login_at": ""},
            {"id": 3, "name": "梁綺雯", "account": "355", "password": UserService.DEFAULT_PASSWORD, "role": "一般人員", "role_level": 2, "active": "TRUE", "must_change_password": "TRUE", "created_at": now, "updated_at": now, "last_login_at": ""},
            {"id": 4, "name": "林志玲", "account": "lin", "password": UserService.DEFAULT_PASSWORD, "role": "一般人員", "role_level": 0, "active": "TRUE", "must_change_password": "TRUE", "created_at": now, "updated_at": now, "last_login_at": ""},
        ]

    @staticmethod
    def _get_sheet_id():
        try:
            return st.secrets.get("google_sheet", {}).get("spreadsheet_id") or st.secrets.get("SHEET_ID")
        except Exception:
            return os.getenv("SHEET_ID")

    @staticmethod
    @st.cache_resource(show_spinner=False)
    def _get_spreadsheet():
        try:
            import gspread
            from google.oauth2.service_account import Credentials

            sheet_id = UserService._get_sheet_id()
            if not sheet_id:
                return None

            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
            service_account_info = st.secrets.get("gcp_service_account", None)
            if not service_account_info:
                return None

            credentials = Credentials.from_service_account_info(service_account_info, scopes=scopes)
            client = gspread.authorize(credentials)
            return client.open_by_key(sheet_id)
        except Exception:
            return None

    @staticmethod
    def _get_worksheet():
        spreadsheet = UserService._get_spreadsheet()
        if not spreadsheet:
            return None
        try:
            return spreadsheet.worksheet(UserService.WORKSHEET_NAME)
        except Exception:
            worksheet = spreadsheet.add_worksheet(title=UserService.WORKSHEET_NAME, rows=200, cols=len(UserService.COLUMNS))
            worksheet.append_row(UserService.COLUMNS)
            worksheet.append_rows([[str(row.get(col, "")) for col in UserService.COLUMNS] for row in UserService.default_users()])
            return worksheet

    @staticmethod
    def using_google_sheet():
        return UserService._get_worksheet() is not None

    @staticmethod
    def _normalize_dataframe(df):
        for col in UserService.COLUMNS:
            if col not in df.columns:
                df[col] = ""
        return df[UserService.COLUMNS].fillna("")

    @staticmethod
    def load_all():
        worksheet = UserService._get_worksheet()
        if worksheet:
            records = worksheet.get_all_records()
            df = pd.DataFrame(records)
            if df.empty:
                df = pd.DataFrame(UserService.default_users())
                UserService.save_all(df.to_dict("records"))
            return UserService._normalize_dataframe(df).to_dict("records")
        return st.session_state.get("user_records_fallback", UserService.default_users())

    @staticmethod
    def save_all(records):
        records = UserService._normalize_dataframe(pd.DataFrame(records)).to_dict("records")
        worksheet = UserService._get_worksheet()
        if worksheet:
            worksheet.clear()
            worksheet.append_row(UserService.COLUMNS)
            if records:
                worksheet.append_rows([[str(row.get(col, "")) for col in UserService.COLUMNS] for row in records])
        else:
            st.session_state.user_records_fallback = records

    @staticmethod
    def get_active_users():
        return [u for u in UserService.load_all() if str(u.get("active", "TRUE")).upper() == "TRUE"]

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
        if not user or str(user.get("active", "TRUE")).upper() != "TRUE":
            return False, "帳號不存在或已停用。", None
        if str(user.get("password", "")) != str(password):
            return False, "密碼錯誤。", None

        records = UserService.load_all()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
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
                row["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                UserService.save_all(records)
                return True, "密碼已更新。"
        return False, "找不到帳號。"

    @staticmethod
    def upsert_user(name, account, role, role_level, active=True, reset_password=False, direct_password=""):
        records = UserService.load_all()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        target = str(account).strip().lower()
        next_id = max([int(float(r.get("id", 0) or 0)) for r in records], default=0) + 1
        for row in records:
            if str(row.get("account", "")).strip().lower() == target:
                row["name"] = name.strip()
                row["role"] = role
                row["role_level"] = int(role_level)
                row["active"] = "TRUE" if active else "FALSE"
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
            "active": "TRUE" if active else "FALSE",
            "must_change_password": "TRUE",
            "created_at": now,
            "updated_at": now,
            "last_login_at": "",
        })
        UserService.save_all(records)
        return "created"


class AnnouncementService:
    """企業布告欄服務：優先使用 Google Sheet，未設定時自動改用 session_state 測試模式。"""

    WORKSHEET_NAME = "Announcements"
    COLUMNS = [
        "id", "title", "content", "level", "author", "created_at", "expires_at",
        "pinned", "active", "attachment_name", "attachment_type", "attachment_base64", "seen_by",
    ]

    @staticmethod
    def is_admin(user=None):
        user = user or st.session_state.get("current_user", "")
        return st.session_state.roles.get(user, 0) >= 2

    @staticmethod
    def _get_sheet_id():
        try:
            return st.secrets.get("google_sheet", {}).get("spreadsheet_id") or st.secrets.get("SHEET_ID")
        except Exception:
            return os.getenv("SHEET_ID")

    @staticmethod
    @st.cache_resource(show_spinner=False)
    def _get_worksheet():
        try:
            import gspread
            from google.oauth2.service_account import Credentials

            sheet_id = AnnouncementService._get_sheet_id()
            if not sheet_id:
                return None

            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
            service_account_info = st.secrets.get("gcp_service_account", None)
            if not service_account_info:
                return None

            credentials = Credentials.from_service_account_info(service_account_info, scopes=scopes)
            client = gspread.authorize(credentials)
            spreadsheet = client.open_by_key(sheet_id)

            try:
                worksheet = spreadsheet.worksheet(AnnouncementService.WORKSHEET_NAME)
            except gspread.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(
                    title=AnnouncementService.WORKSHEET_NAME,
                    rows=200,
                    cols=len(AnnouncementService.COLUMNS),
                )
                worksheet.append_row(AnnouncementService.COLUMNS)
            return worksheet
        except Exception:
            return None

    @staticmethod
    def using_google_sheet():
        return AnnouncementService._get_worksheet() is not None

    @staticmethod
    def _normalize_dataframe(df):
        for col in AnnouncementService.COLUMNS:
            if col not in df.columns:
                df[col] = ""
        return df[AnnouncementService.COLUMNS].fillna("")

    @staticmethod
    def load_all():
        worksheet = AnnouncementService._get_worksheet()
        if worksheet:
            records = worksheet.get_all_records()
            df = pd.DataFrame(records)
            if df.empty:
                df = pd.DataFrame(columns=AnnouncementService.COLUMNS)
            return AnnouncementService._normalize_dataframe(df).to_dict("records")
        return st.session_state.get("announcements_fallback", [])

    @staticmethod
    def save_all(records):
        records = AnnouncementService._normalize_dataframe(pd.DataFrame(records)).to_dict("records")
        worksheet = AnnouncementService._get_worksheet()
        if worksheet:
            worksheet.clear()
            worksheet.append_row(AnnouncementService.COLUMNS)
            if records:
                worksheet.append_rows([[str(row.get(col, "")) for col in AnnouncementService.COLUMNS] for row in records])
        else:
            st.session_state.announcements_fallback = records

    @staticmethod
    def _parse_date(value):
        if not value:
            return None
        try:
            return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
        except Exception:
            return None

    @staticmethod
    def get_active():
        today = date.today()
        active = []
        for ann in AnnouncementService.load_all():
            if str(ann.get("active", "TRUE")).upper() == "FALSE":
                continue
            expires_at = AnnouncementService._parse_date(ann.get("expires_at", ""))
            if expires_at and expires_at < today:
                continue
            active.append(ann)
        return sorted(
            active,
            key=lambda a: (
                str(a.get("pinned", "FALSE")).upper() != "TRUE",
                -int(float(a.get("id", 0) or 0)),
            ),
        )

    @staticmethod
    def create(title, content, level, expires_at, pinned, attachment):
        records = AnnouncementService.load_all()
        next_id = max([int(float(r.get("id", 0) or 0)) for r in records], default=0) + 1

        attachment_name = ""
        attachment_type = ""
        attachment_base64 = ""
        if attachment:
            data = attachment.getvalue()
            attachment_name = attachment.name
            attachment_type = attachment.type or "application/octet-stream"
            attachment_base64 = base64.b64encode(data).decode("utf-8")

        records.append({
            "id": next_id,
            "title": title.strip(),
            "content": content.strip(),
            "level": level,
            "author": st.session_state.current_user,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "expires_at": expires_at.strftime("%Y-%m-%d") if expires_at else "",
            "pinned": "TRUE" if pinned else "FALSE",
            "active": "TRUE",
            "attachment_name": attachment_name,
            "attachment_type": attachment_type,
            "attachment_base64": attachment_base64,
            "seen_by": "",
        })
        AnnouncementService.save_all(records)

    @staticmethod
    def update_flag(announcement_id, field, value):
        records = AnnouncementService.load_all()
        for row in records:
            if int(float(row.get("id", 0) or 0)) == int(announcement_id):
                row[field] = value
        AnnouncementService.save_all(records)

    @staticmethod
    def mark_seen(announcement_id, user):
        records = AnnouncementService.load_all()
        changed = False
        for row in records:
            if int(float(row.get("id", 0) or 0)) == int(announcement_id):
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
    """可重用的 UI 元件"""

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
        """登入入口。未登入時停止後續頁面渲染。"""
        if st.session_state.get("auth_user"):
            return True

        st.title("🔐 鋒霈環境工程部平台登入")
        st.caption("請使用人員帳號(打工號數字)與密碼登入。預設密碼為 0000，首次登入後請立即修改。")

        with st.container(border=True):
            with st.form("login_form"):
                account = st.text_input("帳號")
                password = st.text_input("密碼", type="password")
                submitted = st.form_submit_button("登入", use_container_width=True)

                if submitted:
                    ok, msg, user = UserService.authenticate(account, password)
                    if ok:
                        st.session_state.auth_user = user.get("name")
                        st.session_state.current_user = user.get("name")
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

        if not UserService.using_google_sheet():
            st.info("目前未偵測到 Google Sheet，人員資料會暫存在本次執行階段。部署時請設定 Streamlit Secrets 與 Users 工作表。")

        st.stop()

    @staticmethod
    def render_user_sidebar():
        user = st.session_state.get("auth_user", "")
        user_record = UserService.get_by_name(user) or {}

        st.sidebar.title("導覽控制")
        st.sidebar.success(f"已登入：{user}")
        st.sidebar.caption(f"角色：{user_record.get('role', '未設定')}")

        if st.sidebar.button("登出", use_container_width=True):
            st.session_state.auth_user = None
            st.session_state.current_user = ""
            st.rerun()

        if str(user_record.get("must_change_password", "FALSE")).upper() == "TRUE":
            st.sidebar.warning("你的帳號仍使用預設密碼，請先修改密碼。")

        with st.sidebar.expander("🔑 修改我的密碼", expanded=str(user_record.get("must_change_password", "FALSE")).upper() == "TRUE"):
            with st.form("change_my_password_form"):
                old_password = st.text_input("原密碼", type="password")
                new_password = st.text_input("新密碼", type="password")
                confirm_password = st.text_input("確認新密碼", type="password")
                submitted = st.form_submit_button("更新密碼", use_container_width=True)
                if submitted:
                    ok, msg = UserService.change_password(
                        user_record.get("account", ""), old_password, new_password, confirm_password, require_old=True
                    )
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

        if AnnouncementService.is_admin(user):
            with st.sidebar.expander("👥 人員管理", expanded=False):
                users = UserService.load_all()
                st.caption("新增或更新人員。新帳號預設密碼為 0000。")
                with st.form("admin_user_form"):
                    name = st.text_input("姓名")
                    account = st.text_input("帳號（英文/數字，登入用）")
                    role_map = {"一般人員": 0, "主管": 1, "管理員": 2}
                    role = st.selectbox("角色", list(role_map.keys()))
                    active = st.checkbox("啟用帳號", value=True)
                    direct_password = st.text_input("直接設定密碼（留空則新帳號預設 0000）", type="password")
                    reset_password = st.checkbox("重設密碼為 0000", value=False)
                    submitted = st.form_submit_button("新增 / 更新人員", use_container_width=True)
                    if submitted:
                        if not name.strip() or not account.strip():
                            st.warning("請輸入姓名與帳號。")
                        else:
                            result = UserService.upsert_user(name, account, role, role_map[role], active, reset_password, direct_password)
                            st.success("人員已新增。" if result == "created" else "人員資料已更新。")
                            st.rerun()

                st.divider()
                for u in users:
                    active_text = "啟用" if str(u.get("active", "TRUE")).upper() == "TRUE" else "停用"
                    default_text = "｜需改密碼" if str(u.get("must_change_password", "FALSE")).upper() == "TRUE" else ""
                    st.caption(f"{u.get('name')} / {u.get('account')} / {u.get('role')} / {active_text}{default_text}")

    @staticmethod
    def get_active_announcement_count():
        return len(AnnouncementService.get_active())

    @staticmethod
    def render_announcement_board():
        level_icon = {"一般": "📌", "重要": "⚠️", "緊急": "🚨", "維護": "🛠️"}
        level_label = {"一般": "一般公告", "重要": "重要公告", "緊急": "緊急公告", "維護": "維護公告"}
        user = st.session_state.current_user
        is_admin = AnnouncementService.is_admin(user)
        announcements = AnnouncementService.get_active()
        unread_count = AnnouncementService.unread_count(user)

        pinned_titles = [a.get("title", "") for a in announcements if str(a.get("pinned", "FALSE")).upper() == "TRUE"]
        if pinned_titles:
            marquee_text = "　｜　".join([f"📢 {title}" for title in pinned_titles])
            st.markdown(
                f"""
                <div style="overflow:hidden; white-space:nowrap; border:1px solid #e5e7eb; border-radius:10px; padding:10px; margin-bottom:12px;">
                    <marquee behavior="scroll" direction="left" scrollamount="5">{marquee_text}</marquee>
                </div>
                """,
                unsafe_allow_html=True,
            )

        title_col, status_col = st.columns([5, 2])
        with title_col:
            st.subheader("📢 鋒霈環境工程部布告欄")
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

        if is_admin:
            with st.expander("👮 管理員發布公告", expanded=False):
                with st.form("enterprise_announcement_form", clear_on_submit=True):
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
                        if not title.strip() or not content.strip():
                            st.warning("請輸入公告標題與內容。")
                        elif attachment and attachment.size > 5 * 1024 * 1024:
                            st.error("附件超過 5MB，請壓縮後再上傳。")
                        else:
                            AnnouncementService.create(title, content, level, expires_at, pinned, attachment)
                            st.success("公告已發布並寫入布告欄。")
                            st.rerun()
        else:
            st.caption("目前帳號為一般使用者：僅能查看公告，發布與下架需管理員權限。")

        if not announcements:
            st.info("目前沒有有效公告。")
            return

        for ann in announcements:
            ann_id = int(float(ann.get("id", 0) or 0))
            icon = level_icon.get(ann.get("level", "一般"), "📌")
            seen = [x.strip() for x in str(ann.get("seen_by", "")).split(",") if x.strip()]
            is_unread = user not in seen
            pinned_text = "｜📢 跑馬燈置頂" if str(ann.get("pinned", "FALSE")).upper() == "TRUE" else ""
            unread_text = "｜🔔 新公告" if is_unread else ""

            with st.container(border=True):
                st.markdown(f"### {icon} {ann.get('title', '')}")
                st.caption(
                    f"{level_label.get(ann.get('level', '一般'), '一般公告')}{pinned_text}{unread_text}｜"
                    f"發布人：{ann.get('author', '未知')}｜"
                    f"發布時間：{ann.get('created_at', '-')}｜"
                    f"到期日：{ann.get('expires_at', '未設定')}"
                )
                st.write(ann.get("content", ""))

                attachment_name = ann.get("attachment_name", "")
                attachment_type = ann.get("attachment_type", "")
                attachment_base64 = ann.get("attachment_base64", "")
                if attachment_name and attachment_base64:
                    try:
                        raw = base64.b64decode(attachment_base64)
                        if str(attachment_type).startswith("image/"):
                            st.image(raw, caption=attachment_name, use_container_width=False)
                        st.download_button(
                            label=f"📎 下載附件：{attachment_name}",
                            data=raw,
                            file_name=attachment_name,
                            mime=attachment_type or "application/octet-stream",
                            key=f"download_ann_{ann_id}",
                        )
                    except Exception:
                        st.warning("附件資料讀取失敗，請由管理員重新上傳。")

                if is_unread:
                    if st.button("標記已讀", key=f"seen_ann_{ann_id}"):
                        AnnouncementService.mark_seen(ann_id, user)
                        st.rerun()

                if is_admin:
                    b1, b2, b3, _ = st.columns([1.2, 1.2, 1.2, 5])
                    with b1:
                        if st.button("置頂/取消", key=f"pin_ann_{ann_id}"):
                            new_value = "FALSE" if str(ann.get("pinned", "FALSE")).upper() == "TRUE" else "TRUE"
                            AnnouncementService.update_flag(ann_id, "pinned", new_value)
                            st.rerun()
                    with b2:
                        if st.button("立即下架", key=f"off_ann_{ann_id}"):
                            AnnouncementService.update_flag(ann_id, "active", "FALSE")
                            st.rerun()
                    with b3:
                        if st.button("清除已讀", key=f"clear_seen_ann_{ann_id}"):
                            AnnouncementService.update_flag(ann_id, "seen_by", "")
                            st.rerun()


class StreamFlowEngine:
    @staticmethod
    def add_log(task, message):
        if "history" not in task:
            task["history"] = []
        task["history"].append(f"[{datetime.now().strftime('%m-%d %H:%M')}] {st.session_state.current_user} {message}")


class TaskService:
    """處理所有與任務相關的邏輯"""

    @staticmethod
    def get_filtered_tasks(f_assignees, f_tags, tasks=None):
        if tasks is None:
            tasks = st.session_state.tasks
        filtered = []
        for t in tasks:
            if t["status"] != "Active":
                continue
            match_assignee = (not f_assignees) or any(a in f_assignees for a in t.get("assignees", []))
            match_tag = (not f_tags) or (t.get("tags") in f_tags)
            if match_assignee and match_tag:
                filtered.append(t)
        return filtered

    @staticmethod
    def is_task_locked(task):
        locked_by = [t["title"] for t in st.session_state.tasks if t["id"] in task.get("depends_on", []) and t["category"] != "已完成" and t["status"] == "Active"]
        return len(locked_by) > 0, locked_by

    @staticmethod
    def calculate_team_capacity():
        active_tasks = [t for t in st.session_state.tasks if t["status"] == "Active"]
        load_data = []
        for p in st.session_state.partners:
            active_count = len([t for t in active_tasks if p in t.get("assignees", []) and t["category"] == "進行中"])
            ready_count = len([t for t in active_tasks if p in t.get("assignees", []) and t["category"] == "待辦事項"])
            weight = (active_count * 1.0) + (ready_count * 0.3)
            load_data.append({"夥伴": p, "進行中(權重1.0)": active_count, "待辦(權重0.3)": ready_count, "總負載權重": round(weight, 1)})
        return pd.DataFrame(load_data)


class MeetingService:
    @staticmethod
    def get_visible_meetings(target_date=None):
        user = st.session_state.current_user
        role_level = st.session_state.roles.get(user, 0)
        meetings = st.session_state.meetings
        visible = [m for m in meetings if (user in m["attendees"] or role_level > st.session_state.roles.get(m["owner"], 0) or user == m["owner"])]
        if target_date:
            visible = [m for m in visible if m["time"] == target_date]
        return visible


class ApprovalService:
    @staticmethod
    def process_action(approval, action, reason, transfer_to=None):
        now_str = datetime.now().strftime("%m-%d %H:%M")
        if action == "同意":
            approval["status"] = "已同意"
            approval["history"].append(f"[{now_str}] {st.session_state.current_user} 同意。意見: {reason}")
        elif action == "駁回":
            approval["status"] = "已駁回"
            approval["history"].append(f"[{now_str}] {st.session_state.current_user} 駁回。意見: {reason}")
        elif action == "轉交":
            approval["current_signer"] = transfer_to
            approval["history"].append(f"[{now_str}] {st.session_state.current_user} 轉交給 {transfer_to}。意見: {reason}")
