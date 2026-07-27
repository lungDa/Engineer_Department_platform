import streamlit as st
import calendar
from datetime import date

from utils import AppInitializer, ApprovalService, MeetingService, TaskService, ViewComponents

AppInitializer.setup(load_tasks=True, load_meetings=True, load_approvals=True)
st.header("📅 專案行事曆")


f_assignees, f_tags = ViewComponents.render_filters()

nav1, nav2, nav3, nav4 = st.columns([1, 2, 2, 1])

with nav1:
    if st.button("◀ 上個月", use_container_width=True):
        st.session_state.cal_month = 12 if st.session_state.cal_month == 1 else st.session_state.cal_month - 1
        if st.session_state.cal_month == 12:
            st.session_state.cal_year -= 1
        st.rerun()

with nav2:
    st.session_state.cal_year = st.selectbox(
        "年份",
        range(2020, 2030),
        index=st.session_state.cal_year - 2020
    )

with nav3:
    st.session_state.cal_month = st.selectbox(
        "月份",
        range(1, 13),
        index=st.session_state.cal_month - 1
    )

with nav4:
    if st.button("下個月 ▶", use_container_width=True):
        st.session_state.cal_month = 1 if st.session_state.cal_month == 12 else st.session_state.cal_month + 1
        if st.session_state.cal_month == 1:
            st.session_state.cal_year += 1
        st.rerun()

cal = calendar.Calendar(firstweekday=6)
month_days = cal.monthdayscalendar(
    st.session_state.cal_year,
    st.session_state.cal_month
)

# 星期標題
for w_idx, h_col in enumerate(st.columns(7)):
    h_col.markdown(
        f"<p style='text-align:center; font-weight:bold; color:#38bdf8;'>"
        f"{['日','一','二','三','四','五','六'][w_idx]}</p>",
        unsafe_allow_html=True
    )

# 日期格
for week in month_days:
    day_cols = st.columns(7)

    for d_idx, day in enumerate(week):
        with day_cols[d_idx]:
            if day != 0:
                cur_date = date(
                    st.session_state.cal_year,
                    st.session_state.cal_month,
                    day
                )

                day_tasks = TaskService.get_filtered_tasks(
                    f_assignees,
                    f_tags,
                    [t for t in st.session_state.tasks if t['due'] == cur_date]
                )

                day_mtgs = MeetingService.get_visible_meetings(cur_date)
                day_leaves = [
                    a for a in st.session_state.approvals
                    if a.get("type") == "請假單"
                    and a.get("start_date")
                    and a.get("end_date")
                    and a["start_date"] <= cur_date <= a["end_date"]
                ]

                btn_label = f"{day}"
                if len(day_tasks) > 0:
                    btn_label += f"\n(📋 {len(day_tasks)})"
                if len(day_mtgs) > 0:
                    btn_label += f"\n(🤝 {len(day_mtgs)})"
                if len(day_leaves) > 0:
                    btn_label += f"\n(🏖️ {len(day_leaves)})"

                if st.button(
                    btn_label,
                    key=f"day_{day}",
                    use_container_width=True,
                    type="primary" if cur_date == st.session_state.selected_date else "secondary"
                ):
                    st.session_state.selected_date = cur_date
                    st.rerun()

st.divider()

st.subheader(
    f"🔍 {st.session_state.selected_date.strftime('%Y 年 %m 月 %d 日')} 行程細節"
)

# 任務
for t in TaskService.get_filtered_tasks(
    f_assignees,
    f_tags,
    [t for t in st.session_state.tasks if t['due'] == st.session_state.selected_date]
):
    with st.container(border=True):
        st.markdown(f"### 📌 [任務] {t['title']} `[{t['category']}]`")
        st.write(f"**夥伴：** {', '.join(t.get('assignees', []))}")

# 會議
for m in MeetingService.get_visible_meetings(st.session_state.selected_date):
    with st.container(border=True):
        st.markdown(f"### 🤝 [會議] {m['title']}")
        st.write(f"**與會者：** {', '.join(m['attendees'])}")
        if m.get('notes'):
            st.write(f"**紀要：** {m['notes']}")

# 請假：送出後立即顯示，不等待核准。
for a in st.session_state.approvals:
    if (
        a.get("type") == "請假單"
        and a.get("start_date")
        and a.get("end_date")
        and a["start_date"] <= st.session_state.selected_date <= a["end_date"]
    ):
        with st.container(border=True):
            st.markdown(f"### 🏖️ [請假] {a.get('sender', '')}・{a.get('leave_type', '請假')}")
            st.write(
                f"**期間：** {a['start_date'].strftime('%Y-%m-%d')} ～ "
                f"{a['end_date'].strftime('%Y-%m-%d')}"
            )
            st.write(
                f"**時段：** {a.get('start_time', '08:30')} ～ "
                f"{a.get('end_time', '17:30')}（{a.get('leave_hours', 0):g} 小時）"
            )
            if a.get("content"):
                st.write(f"**說明：** {a['content']}")
            st.caption(f"狀態：{a.get('status', '已送出')}")
