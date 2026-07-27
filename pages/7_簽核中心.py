from datetime import date, datetime

import streamlit as st

from utils import AppInitializer, ApprovalService, UserService


AppInitializer.setup(load_tasks=False, load_approvals=True)

st.header("✍️ 簽核中心")
st.caption("第一階段：請假申請。送出成功後立即寫入 Google Sheet 並顯示於專案行事曆。")

all_people = UserService.get_all_partner_names()
leave_time_options = [
    f"{hour:02d}:{minute:02d}"
    for hour in range(8, 18)
    for minute in (0, 30)
    if (hour, minute) >= (8, 30) and (hour, minute) <= (17, 30)
]


def validate_leave_period(start_date, end_date, start_time, end_time, leave_hours):
    if end_date < start_date:
        return "結束日期不可早於開始日期。"
    if start_date == end_date and end_time <= start_time:
        return "同一天請假時，結束時間必須晚於開始時間。"
    if float(leave_hours) < 0.5 or (float(leave_hours) * 2) % 1 != 0:
        return "請假時數最少為 0.5 小時，且只能以 0.5 小時為單位。"
    if start_date == end_date:
        start_minutes = int(start_time[:2]) * 60 + int(start_time[3:])
        end_minutes = int(end_time[:2]) * 60 + int(end_time[3:])
        if float(leave_hours) > (end_minutes - start_minutes) / 60:
            return "請假時數不可超過所選開始與結束時間的時數。"
    return ""

with st.expander("📝 提出請假申請", expanded=True):
    with st.form("leave_request_form", clear_on_submit=False):
        leave_type = st.selectbox(
            "假別",
            ["特休", "事假", "病假", "公假", "婚假", "喪假", "其他"],
        )
        date_col1, date_col2 = st.columns(2)
        with date_col1:
            start_date = st.date_input("開始日期", value=date.today())
        with date_col2:
            end_date = st.date_input("結束日期", value=date.today())
        time_col1, time_col2, hours_col = st.columns(3)
        with time_col1:
            start_time = st.selectbox("開始時間", leave_time_options, index=0)
        with time_col2:
            end_time = st.selectbox(
                "結束時間",
                leave_time_options,
                index=len(leave_time_options) - 1,
            )
        with hours_col:
            leave_hours = st.number_input(
                "請假時數",
                min_value=0.5,
                value=0.5,
                step=0.5,
                format="%.1f",
            )
        content = st.text_area("請假說明")
        notified_users = st.multiselect(
            "被通知者（可新增或減少）",
            all_people,
            help="被通知者只接收通知，不負責核准。",
        )
        account = st.text_input("工號／帳號")
        password = st.text_input("密碼", type="password")

        if st.form_submit_button("送出請假申請", type="primary"):
            period_error = validate_leave_period(
                start_date, end_date, start_time, end_time, leave_hours
            )
            if period_error:
                st.error(period_error)
            elif not notified_users:
                st.error("請至少選擇一位被通知者。")
            else:
                ok, message, user = UserService.authenticate(account, password)
                if not ok:
                    st.error(message)
                else:
                    now_label = datetime.now().strftime("%m-%d %H:%M")
                    new_app = {
                        "type": "請假單",
                        "leave_type": leave_type,
                        "start_date": start_date,
                        "end_date": end_date,
                        "start_time": start_time,
                        "end_time": end_time,
                        "leave_hours": leave_hours,
                        "content": content.strip(),
                        "sender": user.get("name", ""),
                        "sender_account": user.get("account", account),
                        "notified_users": notified_users,
                        "current_signer": "",
                        "status": "已送出",
                        "history": [f"[{now_label}] {user.get('name', '')} 送出請假申請"],
                    }
                    try:
                        ApprovalService.add_approval(
                            new_app,
                            author=user.get("name", ""),
                            account=user.get("account", account),
                        )
                        st.success("請假申請已送出，並立即寫入專案行事曆與 Google Sheet。")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"請假申請寫入失敗：{exc}")

st.divider()
st.subheader("📤 已送出的請假申請")

leave_apps = [
    a for a in st.session_state.approvals
    if a.get("type") == "請假單"
]

if not leave_apps:
    st.info("目前沒有請假申請。")

for approval in sorted(
    leave_apps,
    key=lambda row: (row.get("start_date") or date.min, row.get("id", 0)),
    reverse=True,
):
    completed = ApprovalService.is_completed_leave(approval)
    status_label = "已休完" if completed else approval.get("status", "已送出")
    with st.container(border=True):
        st.markdown(
            f"### 🏖️ {approval.get('sender', '')}・"
            f"{approval.get('leave_type', '請假')}　`{status_label}`"
        )
        st.write(
            f"**日期：** {approval.get('start_date', '')} ～ "
            f"{approval.get('end_date', '')}"
        )
        st.write(
            f"**時段：** {approval.get('start_time', '08:30')} ～ "
            f"{approval.get('end_time', '17:30')}（"
            f"{float(approval.get('leave_hours') or 0):g} 小時）"
        )
        if approval.get("content"):
            st.write(f"**說明：** {approval['content']}")
        st.write(f"**被通知者：** {', '.join(approval.get('notified_users', [])) or '無'}")

        with st.expander("✏️ 修改／刪除"):
            edit_leave_type = st.selectbox(
                "假別",
                ["特休", "事假", "病假", "公假", "婚假", "喪假", "其他"],
                index=(
                    ["特休", "事假", "病假", "公假", "婚假", "喪假", "其他"].index(
                        approval.get("leave_type", "其他")
                    )
                    if approval.get("leave_type") in
                    ["特休", "事假", "病假", "公假", "婚假", "喪假", "其他"]
                    else 6
                ),
                key=f"leave_type_{approval['id']}",
            )
            edit_start = st.date_input(
                "開始日期",
                value=approval.get("start_date") or date.today(),
                key=f"start_{approval['id']}",
            )
            edit_end = st.date_input(
                "結束日期",
                value=approval.get("end_date") or approval.get("start_date") or date.today(),
                key=f"end_{approval['id']}",
            )
            edit_time_col1, edit_time_col2, edit_hours_col = st.columns(3)
            with edit_time_col1:
                stored_start_time = approval.get("start_time") or "08:30"
                edit_start_time = st.selectbox(
                    "開始時間",
                    leave_time_options,
                    index=(
                        leave_time_options.index(stored_start_time)
                        if stored_start_time in leave_time_options else 0
                    ),
                    key=f"start_time_{approval['id']}",
                )
            with edit_time_col2:
                stored_end_time = approval.get("end_time") or "17:30"
                edit_end_time = st.selectbox(
                    "結束時間",
                    leave_time_options,
                    index=(
                        leave_time_options.index(stored_end_time)
                        if stored_end_time in leave_time_options
                        else len(leave_time_options) - 1
                    ),
                    key=f"end_time_{approval['id']}",
                )
            with edit_hours_col:
                edit_leave_hours = st.number_input(
                    "請假時數",
                    min_value=0.5,
                    value=max(0.5, float(approval.get("leave_hours") or 0.5)),
                    step=0.5,
                    format="%.1f",
                    key=f"leave_hours_{approval['id']}",
                )
            edit_content = st.text_area(
                "請假說明",
                value=approval.get("content", ""),
                key=f"content_{approval['id']}",
            )
            edit_notified = st.multiselect(
                "被通知者",
                all_people,
                default=[name for name in approval.get("notified_users", []) if name in all_people],
                key=f"notified_{approval['id']}",
            )
            edit_account = st.text_input("工號／帳號", key=f"account_{approval['id']}")
            edit_password = st.text_input("密碼", type="password", key=f"password_{approval['id']}")

            update_col, delete_col = st.columns(2)
            with update_col:
                if st.button("儲存修改", key=f"update_{approval['id']}", use_container_width=True):
                    ok, message, user = UserService.authenticate(edit_account, edit_password)
                    period_error = validate_leave_period(
                        edit_start,
                        edit_end,
                        edit_start_time,
                        edit_end_time,
                        edit_leave_hours,
                    )
                    if period_error:
                        st.error(period_error)
                    elif not ok:
                        st.error(message)
                    elif not edit_notified:
                        st.error("請至少選擇一位被通知者。")
                    else:
                        try:
                            ApprovalService.update_approval(
                                approval["id"],
                                {
                                    "leave_type": edit_leave_type,
                                    "start_date": edit_start,
                                    "end_date": edit_end,
                                    "start_time": edit_start_time,
                                    "end_time": edit_end_time,
                                    "leave_hours": edit_leave_hours,
                                    "content": edit_content.strip(),
                                    "notified_users": edit_notified,
                                },
                                user.get("account", edit_account),
                            )
                            st.success("假單與專案行事曆已同步更新。")
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))

            with delete_col:
                if completed:
                    st.button(
                        "已休完，禁止刪除",
                        key=f"delete_disabled_{approval['id']}",
                        disabled=True,
                        use_container_width=True,
                    )
                elif st.button(
                    "刪除假單",
                    key=f"delete_{approval['id']}",
                    use_container_width=True,
                ):
                    ok, message, user = UserService.authenticate(edit_account, edit_password)
                    if not ok:
                        st.error(message)
                    else:
                        try:
                            ApprovalService.delete_approval(
                                approval["id"],
                                user.get("account", edit_account),
                            )
                            st.success("假單已從簽核中心與專案行事曆刪除。")
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))

        with st.expander("📜 操作紀錄"):
            for entry in approval.get("history", []):
                st.caption(entry)
