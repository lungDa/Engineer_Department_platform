import streamlit as st
from utils import AppInitializer

# 1. 統籌全局設定
st.set_page_config(page_title="StreamFlow 專業系統", layout="wide")

# 2. 確保環境初始化 (防禦性程式設計)
AppInitializer.setup()

# 3. 呈現首頁/大門頁面
st.title("🚀 歡迎使用 StreamFlow 專業任務管理系統")
st.write("---")
st.write("這是一個整合了專案管理、會議系統、簽核流程與效率分析的企業級儀表板。")
st.write("請使用側邊欄選擇功能模組。")

# 顯示當前系統概況，讓 app.py 更有價值
st.subheader("系統狀態概覽")
st.metric("目前任務總數", len(st.session_state.tasks))
st.metric("目前使用者", st.session_state.current_user)

st.sidebar.title("導覽控制")
st.session_state.current_user = st.sidebar.selectbox("👤 當前操作者", st.session_state.partners)


# app.py 底部加入此區塊
st.sidebar.divider()
if st.sidebar.button("📝 快速建立任務", use_container_width=True):
    st.session_state.show_add_task = True

if st.session_state.get('show_add_task', False):
    with st.sidebar.container(border=True):
        st.subheader("📝 新增專案任務")
        with st.form("add_task_form"):
            t_title = st.text_input("任務名稱")
            t_cat = st.selectbox("分類", st.session_state.categories)
            t_due = st.date_input("排程日期", st.session_state.selected_date)
            t_assign = st.multiselect("👥 指派", st.session_state.partners)
            
            # --- 補上這兩行 ---
            col1, col2 = st.columns(2)
            with col1: t_imp = st.selectbox("重要度", ["高", "低"])
            with col2: t_urg = st.selectbox("緊急度", ["高", "低"])
            
            if st.form_submit_button("建立任務") and t_title:
                from utils import StreamFlowEngine as engine
                new_t = {
                    "id": len(st.session_state.tasks) + 1,
                    "title": t_title,
                    "category": t_cat,
                    "due": t_due,
                    "assignees": t_assign,
                    "status": "Active",
                    "importance": t_imp,  # 存入重要度
                    "urgency": t_urg,      # 存入緊急度
                    "history": []
                }
                engine.add_log(new_t, "透過側邊欄建立任務")
                st.session_state.tasks.append(new_t)
                st.session_state.show_add_task = False
                st.rerun()