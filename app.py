import streamlit as st

from services.diagnostics_service import DiagnosticsService
from utils import AppInitializer, ViewComponents, TaskService, StreamFlowEngine as engine, UserService, SheetDB

st.set_page_config(page_title="鋒霈 工程部 專業系統", layout="wide")

AppInitializer.setup()
ViewComponents.render_public_sidebar()

title_col, dev_col = st.columns([8, 1])
with title_col:
    st.title("🚀 歡迎使用 鋒霈 工程一部 專業任務管理系統")
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
    st.caption("集中檢查 Google Sheet、LINE Official Account、Render API、AI 等外部服務連線狀態。")

    action_col_1, action_col_2 = st.columns([2, 1])
    with action_col_1:
        run_check = st.button("🔍 執行完整系統診斷", width="stretch")
    with action_col_2:
        if st.button("🧹 清除 Google Sheet 快取", width="stretch"):
            DiagnosticsService.clear_cache()
            st.success("已清除 Google Sheet 快取。")
            st.rerun()

    if run_check or "enterprise_diagnostics_report" not in st.session_state:
        with st.spinner("正在執行系統診斷..."):
            st.session_state["enterprise_diagnostics_report"] = DiagnosticsService.system_report()

    report = st.session_state["enterprise_diagnostics_report"]

    st.markdown("##### Enterprise Health Check")
    score_col, time_col, pass_col = st.columns(3)
    score_col.metric("System Score", f"{report['score']} / 100")
    time_col.metric("診斷時間", report["generated_at"])
    pass_col.metric("通過項目", f"{report['passed']} / {report['total']}")

    st.write("---")

    tab_sheet, tab_line, tab_render, tab_ai, tab_report = st.tabs(
        [
            "🟢 Google Sheet",
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
                developer_password = st.text_input(
                    "請輸入 Users 人員清單中的開發者密碼",
                    type="password",
                    help="請在 Google Sheet 的 Users 工作表建立開發者帳號，role 設為「開發者」或 role_level 設為 9 以上。",
                )
                submitted = st.form_submit_button("顯示系統連線診斷")
                if submitted:
                    ok, msg = UserService.verify_developer_password(developer_password)
                    if ok:
                        st.session_state["developer_diagnostics_unlocked"] = True
                        st.success("開發者驗證成功。")
                        st.rerun()
                    else:
                        st.error(msg)
        else:
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.success("開發者診斷模式已啟用。")
            with col_b:
                if st.button("登出診斷", width="stretch"):
                    st.session_state["developer_diagnostics_unlocked"] = False
                    st.session_state["show_developer_panel"] = False
                    st.rerun()

            render_enterprise_diagnostics()

ViewComponents.render_announcement_board()

st.write("---")
st.subheader("系統狀態概覽")
metric1, metric2 = st.columns(2)
with metric1:
    st.metric("目前任務總數", len(st.session_state.tasks))
with metric2:
    st.metric("有效公告數", ViewComponents.get_active_announcement_count())
