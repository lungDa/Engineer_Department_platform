from datetime import date

import streamlit as st

from utils import MeetingService, UserService, current_department
from utils import AppInitializer
from services.notification_service import notification_service

AppInitializer.setup(load_tasks=False, load_meetings=True)

st.header("📅 會議管理系統")


def show_notification_result(result):
    channels = (result.get("data") or {}).get("channels", {})
    labels = {"teams": "Teams", "outlook": "Outlook"}
    for channel, channel_result in channels.items():
        label = labels.get(channel, channel)
        message = channel_result.get("message", "")
        if channel_result.get("skipped"):
            st.info(f"{label}：略過（{message}）")
        elif channel_result.get("ok"):
            st.success(f"{label}：成功")
        else:
            st.warning(f"{label}：失敗（{message}）")


pending_notification = st.session_state.pop("meeting_notification_result", None)
if pending_notification:
    st.markdown("##### 🔔 上次會議通知結果")
    show_notification_result(pending_notification)


with st.expander("➕ 登記新會議", expanded=True):
    all_people = UserService.get_all_partner_names(current_department())
    st.caption(f"目前部門「{current_department()}」的人員會排在最上方，其餘部門人員也可選擇。")
    pick_col, dept_col, all_col, clear_col = st.columns([2.4, 1, 1, 1])
    with pick_col:
        quick_department = st.selectbox("快速選取部門", UserService.get_departments(), key="meeting_quick_department")
    with dept_col:
        st.write("")
        if st.button("選取該部門全員", key="meeting_select_department", width="stretch"):
            selected = st.session_state.get("meeting_attendees", [])
            dept_names = UserService.get_partner_names_by_department(quick_department)
            st.session_state.meeting_attendees = list(dict.fromkeys(selected + dept_names))
            st.rerun()
    with all_col:
        st.write("")
        if st.button("選取所有人", key="meeting_select_all", width="stretch"):
            st.session_state.meeting_attendees = all_people
            st.rerun()
    with clear_col:
        st.write("")
        if st.button("清除選取", key="meeting_clear_all", width="stretch"):
            st.session_state.meeting_attendees = []
            st.rerun()

    with st.form("add_mtg"):
        m_title = st.text_input("會議主題")
        m_time = st.date_input("開會日期", date.today())
        m_attendees = st.multiselect("與會者（可跨部門）", all_people, key="meeting_attendees")
        m_link = st.text_input("連結")
        m_notes = st.text_area("紀要")
        notify_channels = st.multiselect(
            "建立後通知管道",
            ["Teams", "Outlook"],
            default=["Teams", "Outlook"],
            help="Outlook 只寄給人員名單中已設定公司 Email 的與會者。",
        )

        if st.form_submit_button("登記會議") and m_title:
            try:
                meeting = {
                    "title": m_title,
                    "time": m_time,
                    "attendees": m_attendees,
                    "link": m_link,
                    "notes": m_notes,
                    "department": current_department(),
                }
                actor = st.session_state.current_user
                MeetingService.add_meeting(
                    meeting,
                    author=actor,
                    account="",
                )
                result = notification_service.send_meeting_event(
                    event="created",
                    meeting=meeting,
                    actor=actor,
                    channels=[channel.lower() for channel in notify_channels],
                )
                st.session_state["meeting_notification_result"] = result
                st.success("會議已成功建立並寫入 Google Sheet！")
                st.rerun()
            except Exception as e:
                st.error(f"會議寫入失敗：{e}")

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
