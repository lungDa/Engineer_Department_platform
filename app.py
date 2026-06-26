import streamlit as st
from utils import AppInitializer, ViewComponents, TaskService, StreamFlowEngine as engine, UserService

# 1. 統籌全局設定
st.set_page_config(page_title=" 鋒霈  工程部  專業系統", layout="wide")

# 2. 確保環境初始化
AppInitializer.setup()

# 3. 側邊欄：取消全站登入；新增/發布資料時才驗證工號與密碼
ViewComponents.render_public_sidebar()

# 4. 呈現首頁/大門頁面
st.title("🚀 歡迎使用 鋒霈  工程部  專業任務管理系統")
st.write("---")
st.write("這是一個整合了專案管理、會議系統、簽核流程與效率分析的企業級儀表板。")
st.write("請使用側邊欄選擇功能模組。")

# 5. 首頁企業布告欄
ViewComponents.render_announcement_board()

st.write("---")

# 6. 顯示當前系統概況
st.subheader("系統狀態概覽")
metric1, metric2 = st.columns(2)
with metric1:
    st.metric("目前任務總數", len(st.session_state.tasks))
with metric2:
    st.metric("有效公告數", ViewComponents.get_active_announcement_count())

# 7. 快速建立任務
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
                        st.success(f"任務已建立並寫入 Google Sheet。發布人：{author}")
                        st.rerun()
