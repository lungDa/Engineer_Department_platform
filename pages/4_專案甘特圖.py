import math
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from utils import AppInitializer, TaskService, UserService, parse_date, parse_int

st.set_page_config(page_title="專案甘特圖", layout="wide")
st.header("📊 專案甘特圖｜Enterprise Gantt Center")

# V3.4 Turbo：此頁只需要任務資料，不額外載入 Meetings / Approvals。
AppInitializer.setup(load_tasks=True, load_meetings=False, load_approvals=False)

TODAY = date.today()
STATUS_ORDER = ["待辦事項", "進行中", "已完成"]


# =========================================================
# 工具函式
# =========================================================
def _parse_created_date(value, fallback: date) -> date:
    """created_at 可能是 yyyy-mm-dd HH:MM，也可能是空值。"""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return fallback
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except Exception:
            pass
    return fallback


def _status_label(task: dict) -> str:
    if task.get("status") != "Active":
        return "已封存"
    return str(task.get("category") or "待辦事項")


def _risk_level(row: pd.Series) -> str:
    if row["狀態"] == "已完成":
        return "完成"
    if row["逾期天數"] > 0:
        return "逾期"
    if row["剩餘天數"] <= 3:
        return "3日內到期"
    return "正常"


def _progress_to_int(value) -> int:
    return max(0, min(100, parse_int(value, 0)))


def build_gantt_df(tasks: list[dict], duration_days: int) -> pd.DataFrame:
    rows = []
    for task in tasks:
        if not task.get("title"):
            continue

        finish_date = parse_date(task.get("due"), TODAY) or TODAY
        created_date = _parse_created_date(task.get("created_at"), finish_date - timedelta(days=duration_days))

        # 若建立日比到期日還晚，代表資料可能是匯入或舊資料，改用預設工期反推。
        start_date = created_date if created_date <= finish_date else finish_date - timedelta(days=duration_days)
        if start_date == finish_date:
            start_date = finish_date - timedelta(days=1)

        assignees = task.get("assignees") or []
        if isinstance(assignees, str):
            assignees = [x.strip() for x in assignees.split(",") if x.strip()]

        progress = _progress_to_int(task.get("progress", 0))
        status = _status_label(task)
        remaining = (finish_date - TODAY).days
        overdue = max(0, (TODAY - finish_date).days) if status != "已完成" else 0

        rows.append({
            "ID": task.get("id"),
            "任務": str(task.get("title", "")).strip(),
            "專案階段": status,
            "狀態": status,
            "開始日": start_date,
            "到期日": finish_date,
            "甘特結束日": finish_date + timedelta(days=1),
            "負責人": "、".join(assignees) if assignees else "未指派",
            "重要度": task.get("importance", "低"),
            "緊急度": task.get("urgency", "低"),
            "標籤": task.get("tags", ""),
            "進度": progress,
            "剩餘天數": remaining,
            "逾期天數": overdue,
            "備註": task.get("notes", ""),
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["風險"] = df.apply(_risk_level, axis=1)
    df["工期天數"] = [max(1, (end - start).days) for start, end in zip(df["開始日"], df["到期日"])]
    df["完成權重"] = df["進度"] / 100
    df["排序權重"] = df["狀態"].apply(lambda x: STATUS_ORDER.index(x) if x in STATUS_ORDER else 99)
    return df.sort_values(["排序權重", "到期日", "重要度", "緊急度", "任務"]).reset_index(drop=True)


# =========================================================
# 企業版控制列
# =========================================================
with st.container(border=True):
    st.markdown("### 🧭 甘特圖控制台")

    c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.2, 1])
    with c1:
        duration_days = st.slider("無開始日任務的預設工期", min_value=1, max_value=30, value=7, step=1)
    with c2:
        view_mode = st.selectbox("甘特圖分組", ["依專案階段", "依負責人", "依風險", "依重要度"])
    with c3:
        sort_mode = st.selectbox("排序方式", ["到期日優先", "逾期優先", "進度低優先", "工期長優先"])
    with c4:
        show_done = st.toggle("顯示已完成", value=True)

raw_tasks = st.session_state.get("tasks", [])
df = build_gantt_df(raw_tasks, duration_days)

if df.empty:
    st.info("目前沒有任務資料可供生成甘特圖。")
    st.stop()

# =========================================================
# 篩選器
# =========================================================
st.markdown("### 🔎 進階篩選")
filter_box = st.container(border=True)
with filter_box:
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        status_options = sorted(df["狀態"].dropna().unique().tolist())
        default_status = status_options if show_done else [x for x in status_options if x != "已完成"]
        selected_status = st.multiselect("任務狀態", status_options, default=default_status)
    with f2:
        assignee_options = sorted({name for names in df["負責人"] for name in str(names).replace("、", ",").split(",") if name.strip()})
        selected_assignees = st.multiselect("負責人", assignee_options)
    with f3:
        selected_risks = st.multiselect("風險等級", sorted(df["風險"].unique().tolist()), default=sorted(df["風險"].unique().tolist()))
    with f4:
        date_range = st.date_input("到期區間", value=(df["到期日"].min(), df["到期日"].max()))

    keyword = st.text_input("關鍵字搜尋", placeholder="輸入任務名稱、標籤、備註、負責人...")

filtered = df.copy()
if selected_status:
    filtered = filtered[filtered["狀態"].isin(selected_status)]
if selected_risks:
    filtered = filtered[filtered["風險"].isin(selected_risks)]
if selected_assignees:
    pattern = "|".join(selected_assignees)
    filtered = filtered[filtered["負責人"].str.contains(pattern, regex=True, na=False)]
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_filter, end_filter = date_range
    filtered = filtered[(filtered["到期日"] >= start_filter) & (filtered["到期日"] <= end_filter)]
if keyword.strip():
    k = keyword.strip()
    mask = (
        filtered["任務"].str.contains(k, case=False, na=False)
        | filtered["負責人"].str.contains(k, case=False, na=False)
        | filtered["標籤"].astype(str).str.contains(k, case=False, na=False)
        | filtered["備註"].astype(str).str.contains(k, case=False, na=False)
    )
    filtered = filtered[mask]

if sort_mode == "逾期優先":
    filtered = filtered.sort_values(["逾期天數", "到期日"], ascending=[False, True])
elif sort_mode == "進度低優先":
    filtered = filtered.sort_values(["進度", "到期日"], ascending=[True, True])
elif sort_mode == "工期長優先":
    filtered = filtered.sort_values(["工期天數", "到期日"], ascending=[False, True])
else:
    filtered = filtered.sort_values(["到期日", "排序權重"], ascending=[True, True])

# =========================================================
# KPI 儀表板
# =========================================================
st.markdown("### 📌 專案進度總覽")
active_df = filtered[filtered["狀態"] != "已完成"]
completed_df = filtered[filtered["狀態"] == "已完成"]
overdue_df = filtered[filtered["風險"] == "逾期"]
due_soon_df = filtered[filtered["風險"] == "3日內到期"]
avg_progress = int(round(filtered["進度"].mean(), 0)) if not filtered.empty else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("任務總數", len(filtered))
k2.metric("進行中/待辦", len(active_df))
k3.metric("已完成", len(completed_df))
k4.metric("逾期", len(overdue_df), delta=f"{len(overdue_df)} 件", delta_color="inverse")
k5.metric("平均進度", f"{avg_progress}%")

if not filtered.empty and len(due_soon_df) > 0:
    st.warning(f"⚠️ 近 3 日內到期任務：{len(due_soon_df)} 件，建議優先確認負責人與交付狀態。")
if len(overdue_df) > 0:
    st.error(f"🚨 已逾期任務：{len(overdue_df)} 件，建議立即開立追蹤會議或調整資源。")

# =========================================================
# 甘特圖與分析
# =========================================================
tab_gantt, tab_table, tab_risk, tab_capacity = st.tabs(["📊 甘特圖", "📋 任務明細", "🚨 風險清單", "👥 負載分析"])

with tab_gantt:
    if filtered.empty:
        st.info("目前篩選條件下沒有資料。")
    else:
        color_col = {
            "依專案階段": "專案階段",
            "依負責人": "負責人",
            "依風險": "風險",
            "依重要度": "重要度",
        }[view_mode]

        fig = px.timeline(
            filtered,
            x_start="開始日",
            x_end="甘特結束日",
            y="任務",
            color=color_col,
            hover_data={
                "負責人": True,
                "狀態": True,
                "風險": True,
                "進度": ":.0f",
                "剩餘天數": True,
                "逾期天數": True,
                "開始日": True,
                "到期日": True,
                "甘特結束日": False,
            },
            title="企業專案甘特圖",
        )
        fig.update_yaxes(autorange="reversed")
        fig.update_layout(
            height=max(520, min(1100, 120 + len(filtered) * 32)),
            xaxis_title="日期",
            yaxis_title="任務",
            legend_title=view_mode.replace("依", ""),
            margin=dict(l=20, r=20, t=60, b=20),
        )
        fig.add_vline(x=TODAY, line_dash="dash", annotation_text="今日", annotation_position="top")
        st.plotly_chart(fig, use_container_width=True)

with tab_table:
    display_cols = ["ID", "任務", "負責人", "狀態", "風險", "開始日", "到期日", "工期天數", "進度", "重要度", "緊急度", "標籤", "備註"]
    st.dataframe(
        filtered[display_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "進度": st.column_config.ProgressColumn("進度", min_value=0, max_value=100, format="%d%%"),
            "開始日": st.column_config.DateColumn("開始日"),
            "到期日": st.column_config.DateColumn("到期日"),
        },
    )
    csv = filtered[display_cols].to_csv(index=False).encode("utf-8-sig")
    st.download_button("下載甘特任務明細 CSV", data=csv, file_name="enterprise_gantt_tasks.csv", mime="text/csv")

with tab_risk:
    risk_cols = ["ID", "任務", "負責人", "狀態", "風險", "到期日", "剩餘天數", "逾期天數", "進度", "重要度", "緊急度"]
    priority_df = filtered[filtered["風險"].isin(["逾期", "3日內到期"])]
    if priority_df.empty:
        st.success("目前沒有逾期或 3 日內到期的任務。")
    else:
        st.dataframe(
            priority_df.sort_values(["逾期天數", "到期日"], ascending=[False, True])[risk_cols],
            use_container_width=True,
            hide_index=True,
            column_config={"進度": st.column_config.ProgressColumn("進度", min_value=0, max_value=100, format="%d%%")},
        )

with tab_capacity:
    if filtered.empty:
        st.info("目前沒有資料可分析負載。")
    else:
        exploded = filtered.copy()
        exploded["負責人"] = exploded["負責人"].str.replace("、", ",")
        exploded = exploded.assign(負責人=exploded["負責人"].str.split(",")).explode("負責人")
        exploded["負責人"] = exploded["負責人"].str.strip().replace("", "未指派")

        capacity = exploded.groupby("負責人", dropna=False).agg(
            任務數=("任務", "count"),
            逾期數=("逾期天數", lambda s: int((s > 0).sum())),
            平均進度=("進度", "mean"),
            平均剩餘天數=("剩餘天數", "mean"),
        ).reset_index()
        capacity["平均進度"] = capacity["平均進度"].round(0).astype(int)
        capacity["平均剩餘天數"] = capacity["平均剩餘天數"].round(1)

        col_a, col_b = st.columns([1.1, 1])
        with col_a:
            fig_load = px.bar(capacity.sort_values("任務數", ascending=False), x="負責人", y="任務數", title="負責人任務負載")
            st.plotly_chart(fig_load, use_container_width=True)
        with col_b:
            st.dataframe(capacity, use_container_width=True, hide_index=True)
