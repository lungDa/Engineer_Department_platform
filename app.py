import streamlit as st
from utils import AppInitializer, ViewComponents, TaskService, StreamFlowEngine as engine, UserService, SheetDiagnostics, SheetDB

st.set_page_config(page_title="鋒霈 工程部 專業系統", layout="wide")

AppInitializer.setup()
ViewComponents.render_public_sidebar()

title_col, dev_col = st.columns([8, 1])
with title_col:
    st.title("🚀 歡迎使用 鋒霈 工程部 專業任務管理系統")
with dev_col:
    st.write("")
    if st.button("🛠️ 開發者", width="stretch"):
        st.session_state["show_developer_panel"] = not st.session_state.get("show_developer_panel", False)

st.write("---")
st.write("這是一個整合了專案管理、會議系統、簽核流程與效率分析的企業級儀表板。")
st.write("請使用側邊欄選擇功能模組。")

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
                submitted = st.form_submit_button("顯示 Google Sheet 連線診斷")
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

            with st.expander("🩺 Google Sheet 連線診斷", expanded=True):
                if st.button("重新測試連線並清除快取", width="stretch"):
                    SheetDB.clear_cache()
                    st.rerun()

                status = SheetDiagnostics.status()
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("SHEET_ID", "OK" if status["sheet_id_present"] else "未讀到")
                c2.metric("Service Account", "OK" if status["service_account_present"] else "未讀到")
                c3.metric("金鑰格式", "OK" if status.get("service_account_valid") else "異常")
                c4.metric("連線", "OK" if status["connected"] else "失敗")
                st.caption(f"Sheet ID：{status['sheet_id'] or '-'}")
                st.caption(f"Service Account：{status['client_email'] or '-'}")
                st.caption(f"Spreadsheet：{status['spreadsheet_title'] or '-'}")
                if status["error"]:
                    st.error("Google Sheet 連線失敗，詳細訊息如下：")
                    st.code(status["error"], language="text")
                elif status["connected"]:
                    st.success("Google Sheet 已成功連線。")

ViewComponents.render_announcement_board()

st.write("---")
st.subheader("系統狀態概覽")
metric1, metric2 = st.columns(2)
with metric1:
    st.metric("目前任務總數", len(st.session_state.tasks))
with metric2:
    st.metric("有效公告數", ViewComponents.get_active_announcement_count())
