import streamlit as st
from utils import AppInitializer, ViewComponents

# 1. 統籌全局設定
st.set_page_config(page_title="開發工程部平台", layout="wide")

# 2. 確保環境初始化
AppInitializer.setup()

# 3. 側邊欄：全域操作者與快速建立任務
st.sidebar.title("導覽控制")
st.session_state.current_user = st.sidebar.selectbox(
    "👤 當前操作者",
    st.session_state.partners,
    index=st.session_state.partners.index(st.session_state.current_user)
    if st.session_state.current_user in st.session_state.partners else 0,
)

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

            submit_col, cancel_col = st.columns(2)
            with submit_col:
                submitted = st.form_submit_button("建立任務", use_container_width=True)
            with cancel_col:
                cancelled = st.form_submit_button("取消", use_container_width=True)

            if submitted and t_title:
                from utils import StreamFlowEngine as engine

                new_t = {
                    "id": max([t["id"] for t in st.session_state.tasks], default=0) + 1,
                    "title": t_title,
                    "category": t_cat,
                    "due": t_due,
                    "assignees": t_assign,
                    "status": "Active",
                    "progress": 0,
                    "hours_spent": 0.0,
                    "importance": t_imp,
                    "urgency": t_urg,
                    "history": [],
                }
                engine.add_log(new_t, "透過側邊欄建立任務")
                st.session_state.tasks.append(new_t)
                st.session_state.show_add_task = False
                st.rerun()

            if cancelled:
                st.session_state.show_add_task = False
                st.rerun()

# 4. 首頁主內容
st.title("🚀 開發工程部平台")
st.write("---")
st.write("整合專案任務、會議管理、簽核流程與效率分析的部門管理平台。")
st.write("請使用左側選單切換功能模組。")

# 5. 首頁布告欄
ViewComponents.render_announcement_board()

st.divider()

# 6. 系統狀態概覽
st.subheader("系統狀態概覽")
metric1, metric2, metric3 = st.columns(3)
with metric1:
    st.metric("目前任務總數", len(st.session_state.tasks))
with metric2:
    st.metric("布告欄公告數", len(st.session_state.announcements))
with metric3:
    st.metric("目前使用者", st.session_state.current_user)
