import streamlit as st
from utils import AppInitializer, ViewComponents

# 1. 統籌全局設定
st.set_page_config(page_title=" 鋒霈  工程部  專業系統", layout="wide")

# 2. 確保環境初始化
AppInitializer.setup()

# 3. 登入驗證：人員資料由 Google Sheet Users 工作表維護
ViewComponents.render_login_gate()
ViewComponents.render_user_sidebar()

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
metric1, metric2, metric3 = st.columns(3)
with metric1:
    st.metric("目前任務總數", len(st.session_state.tasks))
with metric2:
    st.metric("有效公告數", ViewComponents.get_active_announcement_count())
with metric3:
    st.metric("目前使用者", st.session_state.current_user)

# 7. 快速建立任務
st.sidebar.divider()
if st.sidebar.button("📝 快速建立任務", use_container_width=True):
    st.session_state.show_add_task = True

if st.session_state.get("show_add_task", False):
    with st.sidebar.container(border=True):
        st.subheader("📝 新增專案任務")
        with st.form("add_task_form"):
            t_title = st.text_input("任務名稱")
            t_cat = st.selectbox("分類", st.session_state.categories)
            t_due = st.date_input("排程日期", st.session_state.selected_date)
            t_assign = st.multiselect("👥 指派", st.session_state.partners)

            col1, col2 = st.columns(2)
            with col1:
                t_imp = st.selectbox("重要度", ["高", "低"])
            with col2:
                t_urg = st.selectbox("緊急度", ["高", "低"])

            if st.form_submit_button("建立任務") and t_title:
                from utils import StreamFlowEngine as engine, TaskService
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
                engine.add_log(new_t, "透過側邊欄建立任務")
                TaskService.add_task(new_t)
                st.session_state.show_add_task = False
                st.success("任務已建立並寫入 Google Sheet。")
                st.rerun()
