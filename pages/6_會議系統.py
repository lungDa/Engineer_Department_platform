import streamlit as st
from datetime import date
from utils import AppInitializer, StreamFlowEngine, ViewComponents, TaskService # 根據該頁面需求 import
from utils import MeetingService  # <--- 關鍵：補上這行
AppInitializer.setup()

st.header("📅 會議管理系統")

with st.expander("➕ 登記新會議", expanded=True):
    with st.form("add_mtg"):
        m_title = st.text_input("會議主題")
        m_time = st.date_input("開會日期", date.today())
        m_attendees = st.multiselect("與會者", st.session_state.partners)
        m_link = st.text_input("連結")
        m_notes = st.text_area("紀要")

        if st.form_submit_button("登記會議") and m_title:
            st.session_state.meetings.append({
                "id": len(st.session_state.meetings) + 1,
                "title": m_title,
                "time": m_time,
                "attendees": m_attendees,
                "link": m_link,
                "notes": m_notes,
                "owner": st.session_state.current_user
            })
            st.success("會議已成功建立！")
            st.rerun()

st.divider()

st.subheader("👀 我有權限查看的會議")

visible = MeetingService.get_visible_meetings()

if not visible:
    st.info("目前沒有安排會議。")

for m in visible:
    with st.container(border=True):
        st.markdown(f"### 🗓️ {m['title']}")
        st.caption(f"發起人: {m['owner']} | 日期: {m['time']}")
        st.write(f"**與會者:** {', '.join(m['attendees'])}")

        if m.get('link'):
            st.write(f"**連結:** {m['link']}")

        if m.get('notes'):
            st.write(f"**紀要:** {m['notes']}")