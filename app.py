import streamlit as st
from utils import AppInitializer, ViewComponents, TaskService, StreamFlowEngine as engine, UserService, SheetDiagnostics, SheetDB

st.set_page_config(page_title="鋒霈 工程部 專業系統", layout="wide")

AppInitializer.setup()
ViewComponents.render_public_sidebar()

st.title("🚀 歡迎使用 鋒霈 工程部 專業任務管理系統")
st.write("---")
st.write("這是一個整合了專案管理、會議系統、簽核流程與效率分析的企業級儀表板。")
st.write("請使用側邊欄選擇功能模組。")

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

st.sidebar.divider()
if st.sidebar.button("📝 快速建立任務", width="stretch"):
    st.session_state.show_add_task = True

if st.session_state.get("show_add_task", False):
    with st.sidebar.container(border=True):
        st.subheader("📝 新增專案任務")
        with st.form("add_task_form"):
            publisher_account = st.text_input("發布人工號 / 帳號")
            publisher_password = st.text_input("發布人密碼", type="password")
            t_title = st.text_input("任務名稱")
            t_cat = st.selectbox("分類", st.session_state.categories)
            t_due = st.date_input("排程日期", st.session_state.selected_date)
            t_assign = st.multiselect("👥 指派", st.session_state.partners)

            col1, col2 = st.columns(2)
            with col1:
                t_imp = st.selectbox("重要度", ["高", "低"])
            with col2:
                t_urg = st.selectbox("緊急度", ["高", "低"])

            submitted = st.form_submit_button("建立任務")
            if submitted:
                if not publisher_account.strip() or not publisher_password:
                    st.warning("請輸入發布人的工號與密碼。")
                elif not t_title.strip():
                    st.warning("請輸入任務名稱。")
                else:
                    ok, msg, publisher = UserService.authenticate(publisher_account, publisher_password)
                    if not ok:
                        st.error(msg)
                    else:
                        author = publisher.get("name") or publisher.get("account") or publisher_account
                        account = publisher.get("account") or publisher_account
                        new_t = {
                            "title": t_title,
                            "category": t_cat,
                            "due": t_due,
                            "assignees": t_assign,
                            "status": "Active",
                            "progress": 0,
                            "hours_spent": 0.0,
                            "importance": t_imp,
                            "urgency": t_urg,
                            "tags": "",
                            "notes": "",
                            "depends_on": [],
                            "history": [],
                        }
                        engine.add_log(new_t, "透過側邊欄建立任務", author=author)
                        TaskService.add_task(new_t, author=author, account=account)
                        st.session_state.show_add_task = False
                        st.success(f"任務已建立並寫入資料庫。發布人：{author}")
                        st.rerun()
