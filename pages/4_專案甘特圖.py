import html
import io
import re
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from utils import AppInitializer, parse_date, parse_int

st.set_page_config(page_title="專案甘特圖", layout="wide")

# V8 Enterprise：此頁只需要任務資料，不額外載入 Meetings / Approvals。
AppInitializer.setup(load_tasks=True, load_meetings=False, load_approvals=False)

TODAY = date.today()
STATUS_ORDER = ["待辦事項", "進行中", "已完成", "已封存"]
RISK_ORDER = {"逾期": 0, "今日截止": 1, "3日內到期": 2, "正常": 3, "完成": 4}
STATUS_COLORS = {
    "待辦事項": "#64748B",
    "進行中": "#2563EB",
    "已完成": "#16A34A",
    "已封存": "#475569",
}
RISK_COLORS = {
    "逾期": "#DC2626",
    "今日截止": "#F59E0B",
    "3日內到期": "#EAB308",
    "正常": "#22C55E",
    "完成": "#16A34A",
}
IMPORTANCE_COLORS = {"高": "#DC2626", "中": "#F59E0B", "低": "#2563EB"}


# =========================================================
# Enterprise Dark CSS
# =========================================================
st.markdown(
    """
<style>
.stApp,
section.main,
.main,
.block-container{
    background:#0F172A !important;
    color:#F8FAFC !important;
}
.block-container{
    padding-top:1.1rem;
    padding-bottom:2rem;
}
[data-testid="stSidebar"],
[data-testid="stSidebarContent"]{
    background:#111827 !important;
    color:#F8FAFC !important;
}
h1,h2,h3,h4,h5,h6,p,label,span,div{
    color:#F8FAFC !important;
}
.enterprise-hero{
    background:linear-gradient(135deg,#111827 0%,#1E293B 55%,#0F172A 100%);
    border:1px solid #334155;
    border-radius:22px;
    padding:24px 28px;
    box-shadow:0 18px 42px rgba(0,0,0,.38);
    margin-bottom:18px;
}
.hero-title{
    font-size:30px;
    font-weight:800;
    letter-spacing:.2px;
    margin-bottom:6px;
}
.hero-subtitle{
    color:#CBD5E1 !important;
    font-size:14px;
}
.panel-card{
    background:rgba(30,41,59,.92);
    border:1px solid #334155;
    border-radius:18px;
    padding:18px;
    box-shadow:0 12px 28px rgba(0,0,0,.28);
    margin-bottom:16px;
}
.kpi-grid{
    display:grid;
    grid-template-columns:repeat(6,minmax(120px,1fr));
    gap:14px;
    margin:16px 0 8px 0;
}
.kpi-card{
    background:linear-gradient(180deg,#1E293B 0%,#111827 100%);
    border:1px solid #334155;
    border-left:6px solid var(--accent,#2563EB);
    border-radius:16px;
    padding:16px 16px 14px 16px;
    min-height:110px;
    box-shadow:0 10px 24px rgba(0,0,0,.28);
    transition:all .2s ease;
}
.kpi-card:hover{
    transform:translateY(-3px);
    box-shadow:0 16px 34px rgba(0,0,0,.38);
}
.kpi-label{
    color:#CBD5E1 !important;
    font-size:13px;
    font-weight:700;
    margin-bottom:10px;
}
.kpi-value{
    color:#FFFFFF !important;
    font-size:32px;
    line-height:1;
    font-weight:900;
    margin-bottom:8px;
}
.kpi-note{
    color:#94A3B8 !important;
    font-size:12px;
}
.risk-strip{
    display:grid;
    grid-template-columns:repeat(3,1fr);
    gap:12px;
}
.risk-card{
    background:#111827;
    border:1px solid #334155;
    border-radius:14px;
    padding:12px 14px;
}
.risk-title{
    font-weight:800;
    margin-bottom:6px;
}
.risk-meta{
    color:#CBD5E1 !important;
    font-size:12px;
}
.status-pill{
    display:inline-block;
    padding:4px 10px;
    border-radius:999px;
    color:white !important;
    font-size:12px;
    font-weight:800;
}
.small-muted{
    color:#94A3B8 !important;
    font-size:13px;
}
.stButton > button,
.stDownloadButton > button{
    background:#2563EB !important;
    color:white !important;
    border:1px solid #1D4ED8 !important;
    border-radius:10px !important;
    font-weight:700 !important;
}
.stButton > button:hover,
.stDownloadButton > button:hover{
    background:#1D4ED8 !important;
    border-color:#60A5FA !important;
}
[data-testid="stExpander"],
[data-testid="stForm"],
[data-testid="stVerticalBlockBorderWrapper"]{
    background:#1E293B !important;
    border-color:#334155 !important;
    border-radius:16px !important;
}
.stTabs [data-baseweb="tab-list"]{
    gap:8px;
}
.stTabs [data-baseweb="tab"]{
    background:#1E293B;
    border:1px solid #334155;
    border-radius:12px 12px 0 0;
    color:#CBD5E1 !important;
    padding:10px 16px;
}
.stTabs [aria-selected="true"]{
    background:#2563EB !important;
    color:#FFFFFF !important;
}
[data-testid="stDataFrame"]{
    background:#1E293B !important;
    border:1px solid #334155 !important;
    border-radius:14px !important;
}
input, textarea, [data-baseweb="select"]{
    background:#111827 !important;
    color:#F8FAFC !important;
}
@media(max-width:1200px){
    .kpi-grid{grid-template-columns:repeat(3,1fr);}    
    .risk-strip{grid-template-columns:1fr;}
}
@media(max-width:760px){
    .kpi-grid{grid-template-columns:1fr;}
}
</style>
""",
    unsafe_allow_html=True,
)


# =========================================================
# 工具函式
# =========================================================
def _escape(value) -> str:
    return html.escape(str(value or ""), quote=True)


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


def _progress_to_int(value) -> int:
    return max(0, min(100, parse_int(value, 0)))


def _split_people(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [x.strip() for x in str(value).replace("、", ",").replace(";", ",").split(",") if x.strip()]


def _risk_level(status: str, remaining_days: int, overdue_days: int) -> str:
    if status == "已完成":
        return "完成"
    if overdue_days > 0:
        return "逾期"
    if remaining_days == 0:
        return "今日截止"
    if 0 < remaining_days <= 3:
        return "3日內到期"
    return "正常"


def _risk_score(row: pd.Series) -> int:
    score = 0
    if row["狀態"] != "已完成":
        score += int(row["逾期天數"]) * 18
        if row["風險"] == "今日截止":
            score += 40
        elif row["風險"] == "3日內到期":
            score += 24
        score += max(0, 100 - int(row["進度"])) // 2
    if row["重要度"] == "高":
        score += 35
    elif row["重要度"] == "中":
        score += 18
    if row["緊急度"] == "高":
        score += 25
    elif row["緊急度"] == "中":
        score += 12
    return int(score)


def _project_health(avg_progress: int, overdue_count: int, active_count: int) -> tuple[str, str]:
    if active_count == 0:
        return "完成", "#16A34A"
    overdue_ratio = overdue_count / max(active_count, 1)
    if overdue_ratio >= 0.35 or avg_progress < 35:
        return "高風險", "#DC2626"
    if overdue_ratio >= 0.15 or avg_progress < 60:
        return "需注意", "#F59E0B"
    return "健康", "#16A34A"


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

        assignees = _split_people(task.get("assignees"))
        progress = _progress_to_int(task.get("progress", 0))
        status = _status_label(task)
        remaining = (finish_date - TODAY).days
        overdue = max(0, (TODAY - finish_date).days) if status != "已完成" else 0
        risk = _risk_level(status, remaining, overdue)

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
            "風險": risk,
            "備註": task.get("notes", ""),
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["工期天數"] = [max(1, (end - start).days) for start, end in zip(df["開始日"], df["到期日"])]
    df["完成權重"] = df["進度"] / 100
    df["風險分數"] = df.apply(_risk_score, axis=1)
    df["排序權重"] = df["狀態"].apply(lambda x: STATUS_ORDER.index(x) if x in STATUS_ORDER else 99)
    df["風險排序"] = df["風險"].map(RISK_ORDER).fillna(99).astype(int)
    return df.sort_values(["排序權重", "風險排序", "到期日", "任務"]).reset_index(drop=True)


def render_kpis(filtered: pd.DataFrame) -> None:
    active_df = filtered[filtered["狀態"] != "已完成"]
    completed_df = filtered[filtered["狀態"] == "已完成"]
    overdue_df = filtered[filtered["風險"] == "逾期"]
    due_today_df = filtered[filtered["風險"] == "今日截止"]
    due_soon_df = filtered[filtered["風險"] == "3日內到期"]
    avg_progress = int(round(filtered["進度"].mean(), 0)) if not filtered.empty else 0
    completion_rate = int(round(len(completed_df) / len(filtered) * 100, 0)) if len(filtered) else 0
    owner_count = len({p for names in filtered["負責人"].tolist() for p in _split_people(names)}) if not filtered.empty else 0
    avg_duration = round(float(filtered["工期天數"].mean()), 1) if not filtered.empty else 0
    health, health_color = _project_health(avg_progress, len(overdue_df), len(active_df))

    cards = [
        ("📋 任務總數", len(filtered), f"負責人 {owner_count} 人", "#2563EB"),
        ("🚧 進行中/待辦", len(active_df), "未完成任務", "#0EA5E9"),
        ("✅ 已完成", len(completed_df), f"完成率 {completion_rate}%", "#16A34A"),
        ("🚨 逾期", len(overdue_df), f"今日截止 {len(due_today_df)} 件", "#DC2626"),
        ("⚠️ 3日內到期", len(due_soon_df), "需優先確認", "#F59E0B"),
        ("📈 平均進度", f"{avg_progress}%", f"專案健康：{health}｜平均工期 {avg_duration} 天", health_color),
    ]
    html_cards = "<div class='kpi-grid'>"
    for label, value, note, accent in cards:
        html_cards += f"""
        <div class='kpi-card' style='--accent:{accent};'>
            <div class='kpi-label'>{_escape(label)}</div>
            <div class='kpi-value'>{_escape(value)}</div>
            <div class='kpi-note'>{_escape(note)}</div>
        </div>
        """
    html_cards += "</div>"
    st.markdown(html_cards, unsafe_allow_html=True)


def make_excel_bytes(df: pd.DataFrame, display_cols: list[str]) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df[display_cols].to_excel(writer, sheet_name="GanttTasks", index=False)
        summary = pd.DataFrame({
            "項目": ["任務總數", "逾期", "今日截止", "3日內到期", "平均進度"],
            "數值": [
                len(df),
                int((df["風險"] == "逾期").sum()) if not df.empty else 0,
                int((df["風險"] == "今日截止").sum()) if not df.empty else 0,
                int((df["風險"] == "3日內到期").sum()) if not df.empty else 0,
                int(round(df["進度"].mean(), 0)) if not df.empty else 0,
            ],
        })
        summary.to_excel(writer, sheet_name="Summary", index=False)
    return buffer.getvalue()


def apply_filters(df: pd.DataFrame, selected_status, selected_risks, selected_assignees, date_range, keyword: str) -> pd.DataFrame:
    filtered = df.copy()
    if selected_status:
        filtered = filtered[filtered["狀態"].isin(selected_status)]
    if selected_risks:
        filtered = filtered[filtered["風險"].isin(selected_risks)]
    if selected_assignees:
        pattern = "|".join(re.escape(x) for x in selected_assignees)
        filtered = filtered[filtered["負責人"].str.contains(pattern, regex=True, na=False)]
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_filter, end_filter = date_range
        filtered = filtered[(filtered["到期日"] >= start_filter) & (filtered["到期日"] <= end_filter)]
    if keyword.strip():
        k = keyword.strip()
        mask = (
            filtered["任務"].str.contains(k, case=False, na=False, regex=False)
            | filtered["負責人"].str.contains(k, case=False, na=False, regex=False)
            | filtered["標籤"].astype(str).str.contains(k, case=False, na=False, regex=False)
            | filtered["備註"].astype(str).str.contains(k, case=False, na=False, regex=False)
        )
        filtered = filtered[mask]
    return filtered


def apply_sort(df: pd.DataFrame, sort_mode: str) -> pd.DataFrame:
    if sort_mode == "逾期優先":
        return df.sort_values(["逾期天數", "到期日", "風險分數"], ascending=[False, True, False])
    if sort_mode == "風險分數優先":
        return df.sort_values(["風險分數", "到期日"], ascending=[False, True])
    if sort_mode == "進度低優先":
        return df.sort_values(["進度", "到期日"], ascending=[True, True])
    if sort_mode == "工期長優先":
        return df.sort_values(["工期天數", "到期日"], ascending=[False, True])
    return df.sort_values(["到期日", "排序權重", "風險排序"], ascending=[True, True, True])


# =========================================================
# Header
# =========================================================
st.markdown(
    f"""
<div class="enterprise-hero">
    <div class="hero-title">📊 專案甘特圖｜Enterprise Gantt Center V8</div>
    <div class="hero-subtitle">今日：{TODAY.strftime('%Y/%m/%d')}｜任務時程、逾期風險、負責人負載與交付狀態集中監控</div>
</div>
""",
    unsafe_allow_html=True,
)

# =========================================================
# 控制列
# =========================================================
with st.container(border=True):
    st.markdown("### 🧭 甘特圖控制台")
    c1, c2, c3, c4 = st.columns([1.1, 1.2, 1.2, 1])
    with c1:
        duration_days = st.slider("無開始日任務的預設工期", min_value=1, max_value=30, value=7, step=1)
    with c2:
        view_mode = st.selectbox("甘特圖分組", ["依專案階段", "依負責人", "依風險", "依重要度", "依進度區間"])
    with c3:
        sort_mode = st.selectbox("排序方式", ["到期日優先", "逾期優先", "風險分數優先", "進度低優先", "工期長優先"])
    with c4:
        show_done = st.toggle("顯示已完成", value=True)

raw_tasks = st.session_state.get("tasks", [])
df = build_gantt_df(raw_tasks, duration_days)

if df.empty:
    st.info("目前沒有任務資料可供生成甘特圖。")
    st.stop()

df["進度區間"] = pd.cut(
    df["進度"],
    bins=[-1, 24, 49, 74, 99, 100],
    labels=["0-24%", "25-49%", "50-74%", "75-99%", "100%"],
)

# =========================================================
# 篩選器
# =========================================================
with st.container(border=True):
    st.markdown("### 🔎 進階篩選")
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        status_options = sorted(df["狀態"].dropna().unique().tolist())
        default_status = status_options if show_done else [x for x in status_options if x != "已完成"]
        selected_status = st.multiselect("任務狀態", status_options, default=default_status)
    with f2:
        assignee_options = sorted({name for names in df["負責人"] for name in _split_people(names) if name.strip()})
        selected_assignees = st.multiselect("負責人", assignee_options)
    with f3:
        risk_options = sorted(df["風險"].unique().tolist(), key=lambda x: RISK_ORDER.get(x, 99))
        selected_risks = st.multiselect("風險等級", risk_options, default=risk_options)
    with f4:
        date_range = st.date_input("到期區間", value=(df["到期日"].min(), df["到期日"].max()))
    keyword = st.text_input("關鍵字搜尋", placeholder="輸入任務名稱、標籤、備註、負責人...")

filtered = apply_filters(df, selected_status, selected_risks, selected_assignees, date_range, keyword)
filtered = apply_sort(filtered, sort_mode)

# =========================================================
# KPI Dashboard
# =========================================================
st.markdown("### 📌 專案進度總覽")
render_kpis(filtered)

overdue_df = filtered[filtered["風險"] == "逾期"]
due_today_df = filtered[filtered["風險"] == "今日截止"]
due_soon_df = filtered[filtered["風險"] == "3日內到期"]

if not filtered.empty and len(due_today_df) > 0:
    st.warning(f"⚠️ 今日截止任務：{len(due_today_df)} 件，建議於下班前確認交付狀態。")
if not filtered.empty and len(due_soon_df) > 0:
    st.warning(f"⚠️ 近 3 日內到期任務：{len(due_soon_df)} 件，建議優先確認負責人與資源。")
if len(overdue_df) > 0:
    st.error(f"🚨 已逾期任務：{len(overdue_df)} 件，建議立即開立追蹤會議或調整資源。")

# =========================================================
# Risk Center
# =========================================================
st.markdown("### 🚨 風險中心")
if filtered.empty:
    st.info("目前篩選條件下沒有資料。")
else:
    top_risk = filtered.sort_values(["風險分數", "逾期天數", "到期日"], ascending=[False, False, True]).head(3)
    risk_html = "<div class='risk-strip'>"
    for _, row in top_risk.iterrows():
        color = RISK_COLORS.get(row["風險"], "#2563EB")
        risk_html += f"""
        <div class='risk-card'>
            <div class='risk-title'>{_escape(row['任務'])}</div>
            <div><span class='status-pill' style='background:{color};'>{_escape(row['風險'])}</span></div>
            <div class='risk-meta'>負責人：{_escape(row['負責人'])}</div>
            <div class='risk-meta'>到期：{_escape(row['到期日'])}｜進度 {int(row['進度'])}%｜風險分數 {int(row['風險分數'])}</div>
        </div>
        """
    risk_html += "</div>"
    st.markdown(risk_html, unsafe_allow_html=True)

# =========================================================
# 甘特圖與分析
# =========================================================
tab_gantt, tab_table, tab_risk, tab_capacity, tab_summary = st.tabs(["📊 甘特圖", "📋 任務明細", "🚨 風險清單", "👥 負載分析", "📈 專案分析"])

with tab_gantt:
    if filtered.empty:
        st.info("目前篩選條件下沒有資料。")
    else:
        color_col = {
            "依專案階段": "專案階段",
            "依負責人": "負責人",
            "依風險": "風險",
            "依重要度": "重要度",
            "依進度區間": "進度區間",
        }[view_mode]

        if color_col == "風險":
            color_map = RISK_COLORS
        elif color_col == "重要度":
            color_map = IMPORTANCE_COLORS
        elif color_col == "專案階段":
            color_map = STATUS_COLORS
        else:
            color_map = None

        fig = px.timeline(
            filtered,
            x_start="開始日",
            x_end="甘特結束日",
            y="任務",
            color=color_col,
            color_discrete_map=color_map,
            hover_data={
                "負責人": True,
                "狀態": True,
                "風險": True,
                "風險分數": True,
                "進度": ":.0f",
                "剩餘天數": True,
                "逾期天數": True,
                "開始日": True,
                "到期日": True,
                "甘特結束日": False,
                "進度區間": False,
            },
            title="Enterprise Project Timeline",
        )
        fig.update_yaxes(autorange="reversed")
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0F172A",
            plot_bgcolor="#111827",
            font=dict(color="#F8FAFC"),
            height=max(560, min(1200, 150 + len(filtered) * 34)),
            xaxis_title="日期",
            yaxis_title="任務",
            legend_title=view_mode.replace("依", ""),
            margin=dict(l=20, r=20, t=64, b=20),
            bargap=0.22,
        )
        fig.update_xaxes(showgrid=True, gridcolor="#334155", zeroline=False)
        fig.update_yaxes(showgrid=False)
        today_x = pd.to_datetime(TODAY)
        fig.add_shape(
            type="line",
            x0=today_x,
            x1=today_x,
            y0=0,
            y1=1,
            xref="x",
            yref="paper",
            line=dict(color="#F43F5E", dash="dash", width=2),
        )
        fig.add_annotation(
            x=today_x,
            y=1.02,
            xref="x",
            yref="paper",
            text="今日",
            showarrow=False,
            font=dict(color="#F43F5E", size=13),
            yanchor="bottom",
        )
        st.plotly_chart(fig, use_container_width=True)

with tab_table:
    display_cols = ["ID", "任務", "負責人", "狀態", "風險", "風險分數", "開始日", "到期日", "工期天數", "進度", "重要度", "緊急度", "標籤", "備註"]
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
    c_csv, c_xlsx = st.columns([1, 1])
    with c_csv:
        st.download_button("下載甘特任務明細 CSV", data=csv, file_name="enterprise_gantt_tasks.csv", mime="text/csv")
    with c_xlsx:
        st.download_button(
            "下載甘特任務明細 Excel",
            data=make_excel_bytes(filtered, display_cols),
            file_name="enterprise_gantt_tasks.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

with tab_risk:
    risk_cols = ["ID", "任務", "負責人", "狀態", "風險", "風險分數", "到期日", "剩餘天數", "逾期天數", "進度", "重要度", "緊急度"]
    priority_df = filtered[filtered["風險"].isin(["逾期", "今日截止", "3日內到期"])]
    if priority_df.empty:
        st.success("目前沒有逾期、今日截止或 3 日內到期的任務。")
    else:
        st.dataframe(
            priority_df.sort_values(["風險分數", "逾期天數", "到期日"], ascending=[False, False, True])[risk_cols],
            use_container_width=True,
            hide_index=True,
            column_config={"進度": st.column_config.ProgressColumn("進度", min_value=0, max_value=100, format="%d%%")},
        )

with tab_capacity:
    if filtered.empty:
        st.info("目前沒有資料可分析負載。")
    else:
        exploded = filtered.copy()
        exploded["負責人"] = exploded["負責人"].str.replace("、", ",", regex=False)
        exploded = exploded.assign(負責人=exploded["負責人"].str.split(",")).explode("負責人")
        exploded["負責人"] = exploded["負責人"].str.strip().replace("", "未指派")

        capacity = exploded.groupby("負責人", dropna=False).agg(
            任務數=("任務", "count"),
            逾期數=("逾期天數", lambda s: int((s > 0).sum())),
            高風險數=("風險分數", lambda s: int((s >= 80).sum())),
            平均進度=("進度", "mean"),
            平均剩餘天數=("剩餘天數", "mean"),
        ).reset_index()
        capacity["平均進度"] = capacity["平均進度"].round(0).astype(int)
        capacity["平均剩餘天數"] = capacity["平均剩餘天數"].round(1)

        col_a, col_b = st.columns([1.15, 1])
        with col_a:
            fig_load = px.bar(
                capacity.sort_values("任務數", ascending=False),
                x="負責人",
                y="任務數",
                color="逾期數",
                title="負責人任務負載",
                color_continuous_scale="Reds",
            )
            fig_load.update_layout(template="plotly_dark", paper_bgcolor="#0F172A", plot_bgcolor="#111827", font=dict(color="#F8FAFC"))
            st.plotly_chart(fig_load, use_container_width=True)
        with col_b:
            st.dataframe(capacity.sort_values("任務數", ascending=False), use_container_width=True, hide_index=True)

with tab_summary:
    if filtered.empty:
        st.info("目前沒有資料可分析。")
    else:
        s1, s2 = st.columns(2)
        status_count = filtered.groupby("狀態", dropna=False).size().reset_index(name="任務數")
        risk_count = filtered.groupby("風險", dropna=False).size().reset_index(name="任務數")
        with s1:
            fig_status = px.pie(status_count, values="任務數", names="狀態", title="任務狀態分布", color="狀態", color_discrete_map=STATUS_COLORS)
            fig_status.update_layout(template="plotly_dark", paper_bgcolor="#0F172A", plot_bgcolor="#111827", font=dict(color="#F8FAFC"))
            st.plotly_chart(fig_status, use_container_width=True)
        with s2:
            fig_risk = px.bar(risk_count, x="風險", y="任務數", title="風險分布", color="風險", color_discrete_map=RISK_COLORS)
            fig_risk.update_layout(template="plotly_dark", paper_bgcolor="#0F172A", plot_bgcolor="#111827", font=dict(color="#F8FAFC"))
            st.plotly_chart(fig_risk, use_container_width=True)
