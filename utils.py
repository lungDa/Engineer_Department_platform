import base64
import os
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st


class AppInitializer:
    @staticmethod
    def setup():
        if "tasks" not in st.session_state:
            st.session_state.tasks = [
                {"id": 1, "title": "資料庫設計", "category": "進行中", "due": date.today() + timedelta(days=2), "assignees": ["王大明"], "status": "Active", "progress": 80, "hours_spent": 4.5, "importance": "高", "urgency": "高", "history": []},
                {"id": 2, "title": "API 開發", "category": "待辦事項", "due": date.today() + timedelta(days=5), "assignees": ["陳小華"], "status": "Active", "progress": 0, "hours_spent": 0.0, "importance": "高", "urgency": "低", "history": []},
            ]
            st.session_state.partners = ["王大明", "陳小華", "林志玲", "闕老師"]
            st.session_state.current_user = "闕老師"
            # role 2 = 管理員，可發布/編輯/刪除公告
            st.session_state.roles = {"闕老師": 2, "王大明": 1, "陳小華": 0, "林志玲": 0}
            st.session_state.categories = ["待辦事項", "進行中", "已完成"]
            st.session_state.meetings = []
            st.session_state.approvals = []
            st.session_state.tags_list = ["設計", "開發", "測試"]
            st.session_state.cal_year = date.today().year
            st.session_state.cal_month = date.today().month
            st.session_state.selected_date = date.today()
            st.session_state.announcements_fallback = []


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
            st.subheader("📢 開發工程部布告欄")
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
