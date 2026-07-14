import base64
from datetime import date, datetime, timedelta

import streamlit as st

from services.sheet_db import SheetDB, SheetDiagnostics
from services.core import (
    UserService, TaskService, MeetingService, ApprovalService, AnnouncementService,
    bool_text, parse_int, now_text
)

class ViewComponents:
    @staticmethod
    def require_login():
        """保留舊頁面呼叫名稱，但不再強制全站登入。"""
        ViewComponents.render_public_sidebar()

    @staticmethod
    def render_filters():
        # V3.4 Turbo：篩選選單優先使用 AppInitializer 已快取的人員清單，避免每次展開篩選器重讀 Users。
        partner_options = st.session_state.get("partners") or UserService.get_partner_names()
        tag_options = st.session_state.get("tags_list", [])

        with st.expander("🔍 進階多維度篩選器", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                f_a = st.multiselect("篩選指派對象", partner_options)
            with c2:
                f_t = st.multiselect("篩選標籤", tag_options)
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
        st.sidebar.markdown(
            f"""
            <div class="edp-sidebar-brand">
                <div class="edp-sidebar-title">鋒霈工程部平台</div>
                <div class="edp-sidebar-sub">Project · Task · Meeting · Approval</div>
                <div class="edp-version-pill">● {st.session_state.get('app_version', 'V3.7 Enterprise Theme V1')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.sidebar.caption("請使用上方導覽切換功能模組。")

        # Google Sheet 連線診斷預設完全隱藏。
        # 只有首頁「🛠️ 開發者」驗證成功後，左側才顯示簡要狀態與重新測試按鈕。
        if st.session_state.get("developer_diagnostics_unlocked", False):
            with st.sidebar.expander("🩺 Google Sheet 連線診斷", expanded=False):
                status = SheetDiagnostics.status()
                if status.get("connected"):
                    st.success(f"Google Sheet 已連線：{status.get('spreadsheet_title', '')}")
                else:
                    st.warning("Google Sheet 連線失敗。")
                    if status.get("error"):
                        err = str(status.get("error"))
                        st.caption("連線訊息：" + err[:500])
                    else:
                        st.caption("連線訊息：未知錯誤，請查看首頁開發者診斷面板。")
                if st.button("重新測試 Google Sheet 連線", width="stretch", key="sidebar_retest_google_sheet"):
                    SheetDB.clear_cache()
                    st.rerun()

        with st.sidebar.expander("👥 人員資料提醒", expanded=False):
            st.caption("任務、會議、簽核與公告發布都會檢查 Users 工作表中的工號與密碼。")
            st.caption("以上")

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

        sheet_status = SheetDiagnostics.status()
        if not sheet_status.get("connected"):
            st.info("目前未偵測到 Google Sheet 設定，公告會暫存在本次執行階段。請檢查 Streamlit Secrets 與 Sheet 共用權限。")
            if sheet_status.get("error"):
                with st.expander("Google Sheet 連線訊息", expanded=False):
                    st.code(str(sheet_status.get("error")), language="text")

        with st.expander("📣 發布公告（所有啟用人員皆可發布）", expanded=False):
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
                submitted = st.form_submit_button("發布公告", width="stretch")
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
                            try:
                                AnnouncementService.create(
                                    title,
                                    content,
                                    level,
                                    expires_at,
                                    pinned,
                                    attachment,
                                    author=author,
                                    account=publisher.get("account", publisher_account),
                                )
                                st.success(f"✅ 公告已成功寫入 Google Sheet。發布人：{author}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ 公告寫入 Google Sheet 失敗：{e}")
                                if st.session_state.get("sheet_db_error"):
                                    with st.expander("Google Sheet 寫入錯誤詳情", expanded=False):
                                        st.code(str(st.session_state.get("sheet_db_error")), language="text")

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
                            st.image(raw, caption=attachment_name, width="content")
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
                        if UserService.effective_role_level(admin) < 6:
                            st.error("公告管理需要權限 6 以上。")
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
