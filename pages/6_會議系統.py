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
        auth_col1, auth_col2 = st.columns(2)
        with auth_col1:
            creator_account = st.text_input("建立人工號", key="meeting_creator_account")
        with auth_col2:
            creator_password = st.text_input(
                "建立人密碼",
                type="password",
                key="meeting_creator_password",
            )
        m_title = st.text_input("會議主題")
        m_time = st.date_input("開會日期", date.today())
        m_attendees = st.multiselect("與會者（可跨部門）", all_people, key="meeting_attendees")
        m_link = st.text_input("連結")
        m_notes = st.text_area("紀要")
        notify_channels = st.multiselect(
            "建立後通知管道",
            ["Teams", "Outlook", "LINE"],
            default=["Teams", "Outlook", "LINE"],
            help="Outlook 寄給已設定公司 Email 的與會者；LINE 廣播給官方帳號好友。",
        )

        if st.form_submit_button("登記會議"):
            if not creator_account.strip() or not creator_password:
                st.error("請輸入建立人自己的工號與密碼。")
            elif not m_title.strip():
                st.error("請輸入會議主題。")
            else:
                ok, message, creator = UserService.authenticate(
                    creator_account,
                    creator_password,
                )
                if not ok:
                    st.error(message)
                    st.stop()
                actor = creator.get("name") or creator.get("account") or creator_account
                meeting = {
                    "title": m_title.strip(),
                    "time": m_time,
                    "attendees": m_attendees,
                    "link": m_link.strip(),
                    "notes": m_notes.strip(),
                    "department": current_department(),
                }
                try:
                    MeetingService.add_meeting(
                        meeting,
                        author=actor,
                        account=creator.get("account", creator_account),
                    )
                    result = notification_service.send_meeting_event(
                        event="created",
                        meeting=meeting,
                        actor=actor,
                        channels=[channel.lower() for channel in notify_channels],
                    )
                    st.session_state["meeting_notification_result"] = result
                    st.success(f"會議已成功建立！操作人：{actor}")
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

        meeting_id = int(m.get("id", 0))
        edit_tab, cancel_tab = st.tabs(["✏️ 變更會議", "🚫 取消會議"])

        with edit_tab:
            attendee_options = list(
                dict.fromkeys(list(m.get("attendees") or []) + all_people)
            )
            with st.form(f"edit_meeting_{meeting_id}"):
                edit_auth1, edit_auth2 = st.columns(2)
                with edit_auth1:
                    editor_account = st.text_input(
                        "修改人工號",
                        key=f"meeting_editor_account_{meeting_id}",
                    )
                with edit_auth2:
                    editor_password = st.text_input(
                        "修改人密碼",
                        type="password",
                        key=f"meeting_editor_password_{meeting_id}",
                    )
                edited_title = st.text_input(
                    "會議主題",
                    value=str(m.get("title") or ""),
                    key=f"edit_title_{meeting_id}",
                )
                edited_time = st.date_input(
                    "開會日期",
                    value=m.get("time") or date.today(),
                    key=f"edit_time_{meeting_id}",
                )
                edited_attendees = st.multiselect(
                    "與會者（可跨部門）",
                    attendee_options,
                    default=list(m.get("attendees") or []),
                    key=f"edit_attendees_{meeting_id}",
                )
                edited_link = st.text_input(
                    "連結",
                    value=str(m.get("link") or ""),
                    key=f"edit_link_{meeting_id}",
                )
                edited_notes = st.text_area(
                    "紀要",
                    value=str(m.get("notes") or ""),
                    key=f"edit_notes_{meeting_id}",
                )
                edit_notify_channels = st.multiselect(
                    "變更後通知管道",
                    ["Teams", "Outlook", "LINE"],
                    default=["Teams", "Outlook", "LINE"],
                    key=f"edit_notify_channels_{meeting_id}",
                    help="Outlook 只寄給更新後的與會者，且其人員資料須有公司 Email。",
                )
                update_submitted = st.form_submit_button("儲存會議變更")

            if update_submitted:
                if not editor_account.strip() or not editor_password:
                    st.error("請輸入修改人自己的工號與密碼。")
                elif not edited_title.strip():
                    st.error("會議主題不可空白。")
                else:
                    ok, message, editor = UserService.authenticate(
                        editor_account,
                        editor_password,
                    )
                    if not ok:
                        st.error(message)
                        st.stop()
                    actor = editor.get("name") or editor.get("account") or editor_account
                    try:
                        updated_meeting = MeetingService.update_meeting(
                            meeting_id,
                            {
                                "title": edited_title.strip(),
                                "time": edited_time,
                                "attendees": edited_attendees,
                                "link": edited_link.strip(),
                                "notes": edited_notes.strip(),
                            },
                        )
                        result = notification_service.send_meeting_event(
                            event="updated",
                            meeting=updated_meeting,
                            actor=actor,
                            channels=[
                                channel.lower()
                                for channel in edit_notify_channels
                            ],
                        )
                        st.session_state["meeting_notification_result"] = result
                        st.success(f"會議已成功更新！操作人：{actor}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"會議更新失敗：{e}")

        with cancel_tab:
            st.warning("取消後會從會議清單及 Google Sheet 移除，無法在平台復原。")
            with st.form(f"cancel_meeting_{meeting_id}"):
                cancel_auth1, cancel_auth2 = st.columns(2)
                with cancel_auth1:
                    canceller_account = st.text_input(
                        "刪除／取消人工號",
                        key=f"meeting_canceller_account_{meeting_id}",
                    )
                with cancel_auth2:
                    canceller_password = st.text_input(
                        "刪除／取消人密碼",
                        type="password",
                        key=f"meeting_canceller_password_{meeting_id}",
                    )
                cancel_confirmed = st.checkbox(
                    f"我確認要取消「{m.get('title', '')}」",
                    key=f"cancel_confirmed_{meeting_id}",
                )
                cancel_notify_channels = st.multiselect(
                    "取消後通知管道",
                    ["Teams", "Outlook", "LINE"],
                    default=["Teams", "Outlook", "LINE"],
                    key=f"cancel_notify_channels_{meeting_id}",
                    help="Outlook 會寄給取消前的與會者。",
                )
                cancel_submitted = st.form_submit_button(
                    "確認取消會議",
                    type="primary",
                )

            if cancel_submitted:
                if not canceller_account.strip() or not canceller_password:
                    st.error("請輸入刪除／取消人自己的工號與密碼。")
                elif not cancel_confirmed:
                    st.error("請先勾選取消確認。")
                else:
                    ok, message, canceller = UserService.authenticate(
                        canceller_account,
                        canceller_password,
                    )
                    if not ok:
                        st.error(message)
                        st.stop()
                    actor = (
                        canceller.get("name")
                        or canceller.get("account")
                        or canceller_account
                    )
                    try:
                        cancelled_meeting = MeetingService.cancel_meeting(
                            meeting_id
                        )
                        result = notification_service.send_meeting_event(
                            event="cancelled",
                            meeting=cancelled_meeting,
                            actor=actor,
                            channels=[
                                channel.lower()
                                for channel in cancel_notify_channels
                            ],
                        )
                        st.session_state["meeting_notification_result"] = result
                        st.success(f"會議已取消！操作人：{actor}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"會議取消失敗：{e}")
