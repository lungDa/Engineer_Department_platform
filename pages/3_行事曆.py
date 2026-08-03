import streamlit as st
from config.功能開關 import 功能已開啟, 要求功能開啟
import calendar
from io import BytesIO
from datetime import date

import pandas as pd

from utils import AppInitializer, ApprovalService, MeetingService, TaskService, ViewComponents

要求功能開啟("行事曆")
AppInitializer.setup(load_tasks=True, load_meetings=True, load_approvals=True)
st.header("📅 行事曆")


EXPORT_COLUMNS = [
    "行程類型", "編號", "主旨／假別", "開始日期", "結束日期",
    "開始時間", "結束時間", "時數", "人員", "部門／課別",
    "狀態", "標籤／分類", "說明／紀要", "連結",
]


def _date_text(value):
    return value.strftime("%Y-%m-%d") if isinstance(value, date) else str(value or "")


def _month_contains(value, year, month):
    return isinstance(value, date) and value.year == year and value.month == month


def _period_overlaps_month(start_date, end_date, year, month):
    if not isinstance(start_date, date):
        return False
    end_date = end_date if isinstance(end_date, date) else start_date
    month_start = date(year, month, 1)
    month_end = date(
        year,
        month,
        calendar.monthrange(year, month)[1],
    )
    return start_date <= month_end and end_date >= month_start


def build_export_rows(section, year, month, assignees, tags):
    """依目前分頁、月份及畫面篩選條件建立匯出資料。"""
    rows = []

    if section in ("綜合", "專案"):
        filtered_tasks = TaskService.get_filtered_tasks(
            assignees,
            tags,
            st.session_state.tasks,
        )
        for task in filtered_tasks:
            if not _month_contains(task.get("due"), year, month):
                continue
            rows.append({
                "行程類型": "任務",
                "編號": task.get("id", ""),
                "主旨／假別": task.get("title", ""),
                "開始日期": _date_text(task.get("due")),
                "結束日期": _date_text(task.get("due")),
                "開始時間": "",
                "結束時間": "",
                "時數": "",
                "人員": "、".join(task.get("assignees", [])),
                "部門／課別": task.get("department", ""),
                "狀態": task.get("status", ""),
                "標籤／分類": task.get("tags") or task.get("category", ""),
                "說明／紀要": task.get("description") or task.get("notes", ""),
                "連結": "",
            })

        for meeting in MeetingService.get_visible_meetings():
            if not _month_contains(meeting.get("time"), year, month):
                continue
            rows.append({
                "行程類型": "會議",
                "編號": meeting.get("id", ""),
                "主旨／假別": meeting.get("title", ""),
                "開始日期": _date_text(meeting.get("time")),
                "結束日期": _date_text(meeting.get("time")),
                "開始時間": "",
                "結束時間": "",
                "時數": "",
                "人員": "、".join(meeting.get("attendees", [])),
                "部門／課別": meeting.get("department", ""),
                "狀態": "",
                "標籤／分類": "",
                "說明／紀要": meeting.get("notes", ""),
                "連結": meeting.get("link", ""),
            })

    approval_types = []
    if section in ("綜合", "請假"):
        approval_types.append("請假單")
    if section in ("綜合", "加班"):
        approval_types.append("加班單")

    for approval in st.session_state.approvals:
        if approval.get("type") not in approval_types:
            continue
        if not _period_overlaps_month(
            approval.get("start_date"),
            approval.get("end_date"),
            year,
            month,
        ):
            continue
        rows.append({
            "行程類型": "請假" if approval.get("type") == "請假單" else "加班",
            "編號": approval.get("id", ""),
            "主旨／假別": approval.get("leave_type", ""),
            "開始日期": _date_text(approval.get("start_date")),
            "結束日期": _date_text(approval.get("end_date")),
            "開始時間": approval.get("start_time", ""),
            "結束時間": approval.get("end_time", ""),
            "時數": approval.get("leave_hours", ""),
            "人員": approval.get("sender", ""),
            "部門／課別": approval.get("department", ""),
            "狀態": approval.get("status", ""),
            "標籤／分類": "",
            "說明／紀要": approval.get("content", ""),
            "連結": "",
        })

    return sorted(
        rows,
        key=lambda row: (
            row.get("開始日期", ""),
            row.get("開始時間", ""),
            row.get("行程類型", ""),
            str(row.get("編號", "")),
        ),
    )


def export_files(rows, section):
    frame = pd.DataFrame(rows, columns=EXPORT_COLUMNS)
    csv_data = frame.to_csv(index=False).encode("utf-8-sig")

    excel_data = BytesIO()
    with pd.ExcelWriter(excel_data, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name=section)
        worksheet = writer.book[section]
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions
        for column_cells in worksheet.columns:
            values = [str(cell.value or "") for cell in column_cells]
            width = min(max(max(map(len, values), default=0) + 2, 10), 36)
            worksheet.column_dimensions[column_cells[0].column_letter].width = width

    return csv_data, excel_data.getvalue()


f_assignees, f_tags = ViewComponents.render_filters()

schedule_type = st.segmented_control(
    "行事曆分頁",
    ["綜合", "加班", "請假", "專案"],
    default="綜合",
    key="calendar_section",
)
show_tasks = schedule_type in ("綜合", "專案")
show_meetings = schedule_type in ("綜合", "專案")
show_leaves = schedule_type in ("綜合", "請假")
show_overtime = schedule_type in ("綜合", "加班")

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

export_rows = build_export_rows(
    schedule_type,
    st.session_state.cal_year,
    st.session_state.cal_month,
    f_assignees,
    f_tags,
)
csv_data, excel_data = export_files(export_rows, schedule_type)
export_name = (
    f"行事曆_{schedule_type}_"
    f"{st.session_state.cal_year}{st.session_state.cal_month:02d}"
)
export_col1, export_col2, export_col3 = st.columns([1, 1, 2])
with export_col1:
    st.download_button(
        "⬇️ 匯出 Excel",
        data=excel_data,
        file_name=f"{export_name}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        key=f"calendar_export_xlsx_{schedule_type}",
        disabled=not 功能已開啟("行事曆匯出"),
    )
with export_col2:
    st.download_button(
        "⬇️ 匯出 CSV",
        data=csv_data,
        file_name=f"{export_name}.csv",
        mime="text/csv",
        use_container_width=True,
        key=f"calendar_export_csv_{schedule_type}",
        disabled=not 功能已開啟("行事曆匯出"),
    )
with export_col3:
    st.caption(
        f"匯出範圍：{st.session_state.cal_year} 年 "
        f"{st.session_state.cal_month} 月・{schedule_type}・共 {len(export_rows)} 筆"
    )

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

                day_tasks = (
                    TaskService.get_filtered_tasks(
                        f_assignees,
                        f_tags,
                        [t for t in st.session_state.tasks if t['due'] == cur_date]
                    )
                    if show_tasks
                    else []
                )

                day_mtgs = (
                    MeetingService.get_visible_meetings(cur_date)
                    if show_meetings
                    else []
                )
                day_leaves = (
                    [
                        a for a in st.session_state.approvals
                        if a.get("type") == "請假單"
                        and a.get("start_date")
                        and a.get("end_date")
                        and a["start_date"] <= cur_date <= a["end_date"]
                    ]
                    if show_leaves
                    else []
                )
                day_overtime = (
                    [
                        a for a in st.session_state.approvals
                        if a.get("type") == "加班單"
                        and a.get("start_date")
                        and a.get("end_date")
                        and a["start_date"] <= cur_date <= a["end_date"]
                    ]
                    if show_overtime
                    else []
                )

                btn_label = f"{day}"
                if len(day_tasks) > 0:
                    btn_label += f"\n(📋 {len(day_tasks)})"
                if len(day_mtgs) > 0:
                    btn_label += f"\n(🤝 {len(day_mtgs)})"
                if len(day_leaves) > 0:
                    btn_label += f"\n(🏖️ {len(day_leaves)})"
                if len(day_overtime) > 0:
                    btn_label += f"\n(🌙 {len(day_overtime)})"

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
if show_tasks:
    for t in TaskService.get_filtered_tasks(
        f_assignees,
        f_tags,
        [t for t in st.session_state.tasks if t['due'] == st.session_state.selected_date]
    ):
        with st.container(border=True):
            st.markdown(f"### 📌 [任務] {t['title']} `[{t['category']}]`")
            st.write(f"**夥伴：** {', '.join(t.get('assignees', []))}")

# 會議
if show_meetings:
    for m in MeetingService.get_visible_meetings(st.session_state.selected_date):
        with st.container(border=True):
            st.markdown(f"### 🤝 [會議] {m['title']}")
            st.write(f"**與會者：** {', '.join(m['attendees'])}")
            if m.get('notes'):
                st.write(f"**紀要：** {m['notes']}")

# 請假：送出後立即顯示，不等待核准。
if show_leaves:
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

# 加班：送出後立即顯示，不等待核准。
if show_overtime:
    for a in st.session_state.approvals:
        if (
            a.get("type") == "加班單"
            and a.get("start_date")
            and a.get("end_date")
            and a["start_date"] <= st.session_state.selected_date <= a["end_date"]
        ):
            with st.container(border=True):
                st.markdown(f"### 🌙 [加班] {a.get('sender', '')}・{a.get('leave_type', '平日加班')}")
                st.write(
                    f"**日期：** {a['start_date'].strftime('%Y-%m-%d')} ～ "
                    f"{a['end_date'].strftime('%Y-%m-%d')}"
                )
                st.write(
                    f"**時段：** {a.get('start_time', '')} ～ "
                    f"{a.get('end_time', '')}（{a.get('leave_hours', 0):g} 小時）"
                )
                if a.get("content"):
                    st.write(f"**加班事由：** {a['content']}")
                st.caption(f"狀態：{a.get('status', '已送出')}")
