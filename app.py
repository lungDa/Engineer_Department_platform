import streamlit as st

from services.diagnostics_service import DiagnosticsService
from utils import AppInitializer, ViewComponents, TaskService, StreamFlowEngine as engine, UserService, SheetDB
from config.departments import DEPARTMENTS
from config.roles import ROLE_LEVELS

st.set_page_config(page_title="鋒霈_工程一部 管理平台", layout="wide")

AppInitializer.setup(load_tasks=False, load_meetings=False, load_approvals=False)
ViewComponents.render_public_sidebar()

title_col, dev_col = st.columns([8, 1])
with title_col:
    st.title("🚀 歡迎使用 工程一部_管理平台")
with dev_col:
    st.write("")
    if st.button("🛠️ 開發者", width="stretch"):
        st.session_state["show_developer_panel"] = not st.session_state.get("show_developer_panel", False)

st.write("---")
st.write("這是一個整合了專案管理、會議系統、簽核流程與效率分析的企業級儀表板。")
st.write("請使用側邊欄選擇功能模組。")


def render_status_badge(ok: bool, ok_text: str = "正常", fail_text: str = "異常"):
    if ok:
        st.success(f"🟢 {ok_text}")
    else:
        st.error(f"🔴 {fail_text}")


def render_enterprise_diagnostics():
    st.markdown("#### 🛠 Enterprise System Diagnostics")
    st.caption("集中檢查 Google Sheet、Microsoft 365 通知、LINE、Render API、AI 等外部服務狀態。")

    action_col_1, action_col_2 = st.columns([2, 1])
    with action_col_1:
        run_check = st.button("🔍 執行完整系統診斷", width="stretch")
    with action_col_2:
        if st.button("🧹 清除 Google Sheet 快取", width="stretch"):
            DiagnosticsService.clear_cache()
            st.success("已清除 Google Sheet 快取。")
            st.rerun()

    cached_report = st.session_state.get("enterprise_diagnostics_report")
    report_is_current = (
        isinstance(cached_report, dict)
        and cached_report.get("schema_version") == DiagnosticsService.REPORT_SCHEMA_VERSION
        and "microsoft365" in cached_report
    )

    if run_check or not report_is_current:
        with st.spinner("正在執行系統診斷..."):
            st.session_state["enterprise_diagnostics_report"] = DiagnosticsService.system_report()

    report = st.session_state["enterprise_diagnostics_report"]

    st.markdown("##### Enterprise Health Check")
    score_col, time_col, pass_col = st.columns(3)
    score_col.metric("System Score", f"{report['score']} / 100")
    time_col.metric("診斷時間", report["generated_at"])
    pass_col.metric("通過項目", f"{report['passed']} / {report['total']}")

    st.write("---")

    tab_sheet, tab_m365, tab_line, tab_render, tab_ai, tab_report = st.tabs(
        [
            "🟢 Google Sheet",
            "🟣 Microsoft 365",
            "🟩 LINE Official Account",
            "🟦 Render API",
            "🟡 AI",
            "📋 Report",
        ]
    )

    with tab_sheet:
        google = report["google_sheet"]
        st.markdown("##### 🟢 Google Sheet 連線診斷")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("SHEET_ID", "OK" if google["sheet_id_present"] else "未讀到")
        c2.metric("Service Account", "OK" if google["service_account_present"] else "未讀到")
        c3.metric("金鑰格式", "OK" if google["service_account_valid"] else "異常")
        c4.metric("連線", "OK" if google["connected"] else "失敗")

        st.caption(f"Sheet ID：{google['sheet_id'] or '-'}")
        st.caption(f"Service Account：{google['client_email'] or '-'}")
        st.caption(f"Spreadsheet：{google['spreadsheet_title'] or '-'}")

        if google["error"]:
            st.error("Google Sheet 連線失敗，詳細訊息如下：")
            st.code(google["error"], language="text")
        elif google["connected"]:
            st.success("Google Sheet 已成功連線。")

        st.info("目前 Google Sheet 快取由 services/sheet_db.py 控制，Tasks TTL 較短，Users / Categories / Tags TTL 較長。")

    with tab_m365:
        # Defensive fallback: an incomplete or legacy cached report must never
        # crash the whole Streamlit app.
        m365 = report.get("microsoft365") or DiagnosticsService.microsoft365_status()
        st.markdown("##### 🟣 Microsoft 365 通知")
        c1, c2, c3 = st.columns(3)
        c1.metric("Teams 通知", "OK" if m365["teams_configured"] else "未設定")
        c2.metric("Outlook 寄信", "OK" if m365["outlook_configured"] else "未設定")
        c3.metric("共用驗證 Token", "OK" if m365["webhook_token_present"] else "選用")
        st.caption(f"Teams Webhook：{m365['teams_webhook_masked']}")
        st.caption(f"Outlook Webhook：{m365['outlook_webhook_masked']}")
        st.info("Webhook 網址視同密碼，請只放在 Render 環境變數，不要寫入 GitHub。")

        features = m365.get("features", {})
        f1, f2, f3 = st.columns(3)
        f1.metric("Teams Flow", "READY" if features.get("teams_channel_notification") else "OFF")
        f2.metric("Outlook Flow", "READY" if features.get("outlook_send_mail") else "OFF")
        f3.metric("事件觸發", "已接上" if features.get("event_triggers_connected") else "下一階段")

    with tab_line:
        line = report["line"]
        st.markdown("##### 🟩 LINE Official Account")
        c1, c2, c3 = st.columns(3)
        c1.metric("LINE 設定", "OK" if line["configured"] else "未完成")
        c2.metric("Channel Secret", "OK" if line["channel_secret_present"] else "未設定")
        c3.metric("Access Token", "OK" if line["channel_access_token_present"] else "未設定")

        st.caption(f"Channel Secret：{line['channel_secret_masked']}")
        st.caption(f"Access Token：{line['channel_access_token_masked']}")

        if line["webhook_url"]:
            st.markdown("Webhook URL")
            st.code(line["webhook_url"], language="text")
        else:
            st.warning("API_BASE_URL 尚未設定，因此無法產生 Webhook URL。")

        features = line.get("features", {})
        f1, f2, f3, f4 = st.columns(4)
        f1.metric("Webhook", "ON" if features.get("webhook") else "OFF")
        f2.metric("Signature", "ON" if features.get("signature_validation") else "OFF")
        f3.metric("Reply", "ON" if features.get("reply") else "OFF")
        f4.metric("Push", "ON" if features.get("push") else "OFF")

        st.info("請到 LINE Developers 將 Webhook URL 設為上方網址，並開啟 Use webhook。")

    with tab_render:
        render = report["render_api"]
        st.markdown("##### 🟦 Render API")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("API URL", "OK" if render["configured"] else "未設定")
        c2.metric("Health", "OK" if render["health_ok"] else "失敗")
        c3.metric("Ready", "OK" if render["ready_ok"] else "失敗")
        c4.metric("Latency", f"{render['latency_ms']} ms" if render["latency_ms"] is not None else "-")

        st.caption(f"API Base URL：{render['base_url'] or '-'}")
        st.caption(f"Version：{render['version']}")
        st.caption(f"Environment：{render['environment']}")

        if render["health_url"]:
            st.markdown("Health URL")
            st.code(render["health_url"], language="text")

        if render["error"]:
            st.error(render["error"])
        elif render["health_ok"]:
            st.success("Render API Health Check 正常。")

    with tab_ai:
        ai = report["ai"]
        st.markdown("##### 🟡 AI Service")
        c1, c2 = st.columns(2)
        c1.metric("OpenAI API Key", "OK" if ai["openai_api_key_present"] else "未設定")
        c2.metric("AI Service", "Ready" if ai["configured"] else "Not Configured")
        st.caption(f"OpenAI API Key：{ai['openai_api_key_masked']}")
        st.info("V5.2.0 將啟用 AI 任務分析、設備查詢與自然語言問答。")

    with tab_report:
        st.markdown("##### 📋 System Report JSON")
        st.json(report)


if st.session_state.get("show_developer_panel", False):
    with st.container(border=True):
        st.markdown("#### 🛠️ 開發者工具")
        if not st.session_state.get("developer_diagnostics_unlocked", False):
            with st.form("developer_diagnostics_login"):
                developer_password = st.text_input("開發者密碼", type="password")
                st.caption("首頁只驗證開發者。其他角色會在使用需要權限的功能時才驗證。")
                submitted = st.form_submit_button("進入開發者模式")
                if submitted:
                    ok, msg = UserService.verify_developer_password(developer_password)
                    if ok:
                        st.session_state["personnel_management_unlocked"] = True
                        st.session_state["management_user"] = "開發者"
                        st.session_state["management_role_level"] = 9
                        st.session_state["developer_diagnostics_unlocked"] = True
                        st.success("開發者驗證成功。")
                        st.rerun()
                    else:
                        st.error(msg)
        else:
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.success(
                    "開發者模式已啟用｜權限 9"
                )
            with col_b:
                if st.button("登出開發者模式", width="stretch"):
                    st.session_state["personnel_management_unlocked"] = False
                    st.session_state["developer_diagnostics_unlocked"] = False
                    st.session_state.pop("management_user", None)
                    st.session_state.pop("management_role_level", None)
                    st.session_state["show_developer_panel"] = False
                    st.rerun()

            management_tab, diagnostics_tab = st.tabs(["👥 人員與權限管理", "🩺 系統診斷"])
            with management_tab:
                st.caption("人員依課別分組；任務、會議與簽核的人名選單只顯示目前課別成員。")
                selected_department = st.selectbox("管理課別", DEPARTMENTS, key="developer_manage_department")
                users = UserService.get_users_by_department(selected_department, active_only=False)
                operator_level = int(st.session_state.get("management_role_level", 0) or 0)
                manageable_users = [
                    user for user in users
                    if UserService.effective_role_level(user) <= operator_level
                ]
                if users:
                    st.dataframe(
                        [{
                            "課別": u.get("department") or "儀電規劃課",
                            "姓名": u.get("name", ""), "帳號": u.get("account", ""),
                            "角色": u.get("role", ""), "權限等級": u.get("role_level", 0),
                            "啟用": u.get("active", "TRUE"),
                        } for u in users],
                        width="stretch", hide_index=True,
                    )
                else:
                    st.info("此課別尚無人員。")

                with st.expander("📊 全課別人數總覽", expanded=False):
                    department_counts = [
                        {
                            "課別": department,
                            "啟用人數": len(UserService.get_users_by_department(department)),
                            "全部人數（含停用）": len(UserService.get_users_by_department(department, active_only=False)),
                        }
                        for department in DEPARTMENTS
                    ]
                    st.dataframe(department_counts, width="stretch", hide_index=True)

                with st.expander("➕ 新增或調整人員", expanded=not users):
                    with st.form("developer_user_editor"):
                        name = st.text_input("姓名")
                        account = st.text_input("帳號（既有帳號會更新資料）")
                        allowed_roles = [name for name, level in ROLE_LEVELS.items() if level <= operator_level]
                        role = st.selectbox("角色／權限", allowed_roles, index=len(allowed_roles) - 1)
                        active = st.checkbox("啟用帳號", value=True)
                        direct_password = st.text_input("設定密碼（新增時空白為 0000）", type="password")
                        if st.form_submit_button("儲存人員", width="stretch"):
                            if not name.strip() or not account.strip():
                                st.error("姓名與帳號為必填。")
                            else:
                                existing_user = UserService.get_by_account(account)
                                existing_level = UserService.effective_role_level(existing_user)
                                if existing_user and existing_level > operator_level:
                                    st.error("不可修改權限高於目前登入者的人員。")
                                else:
                                    result = UserService.upsert_user(
                                        name=name, account=account, role=role,
                                        role_level=ROLE_LEVELS[role], active=active,
                                        direct_password=direct_password,
                                        department=selected_department,
                                    )
                                    st.success("人員已新增。" if result == "created" else "人員資料與權限已更新。")
                                    st.rerun()

                with st.expander("🗑️ 刪除人員"):
                    deletable = {f"{u.get('name')}（{u.get('account')}）": u.get("account") for u in manageable_users}
                    if deletable:
                        target_label = st.selectbox("選擇人員", list(deletable.keys()))
                        confirm = st.checkbox("我確認要永久刪除此人員")
                        if st.button("刪除人員", type="primary", disabled=not confirm):
                            ok, msg = UserService.delete_user(deletable[target_label])
                            (st.success if ok else st.error)(msg)
                            if ok:
                                st.rerun()
                    else:
                        st.info("沒有可刪除的人員。")

            with diagnostics_tab:
                if st.session_state.get("developer_diagnostics_unlocked", False):
                    render_enterprise_diagnostics()
                else:
                    st.warning("系統診斷與其他開發者功能僅限開發者（權限 9）使用。")

ViewComponents.render_announcement_board()

st.write("---")
st.subheader("系統狀態概覽")
metric1, metric2 = st.columns(2)
with metric1:
    st.metric("目前任務總數", len(st.session_state.tasks))
with metric2:
    st.metric("有效公告數", ViewComponents.get_active_announcement_count())
