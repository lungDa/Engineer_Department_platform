# -*- coding: utf-8 -*-
"""
pages/2_艾森豪矩陣.py
Enterprise Matrix Dashboard V6.0

設計目標：
- 保留既有 StreamFlow / utils 架構
- 企業版 UI：Dashboard Header / KPI / Eisenhower Matrix / Right Insight Panel
- 每張任務卡一次輸出完整 HTML，避免 Streamlit 顯示原始 HTML 片段
- 支援搜尋、篩選、排序、逾期風險、CSV 匯出
"""

from __future__ import annotations

import html
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Tuple

import pandas as pd
import streamlit as st
from utils import AppInitializer


# ============================================================
# Page Config / Init
# ============================================================

st.set_page_config(
    page_title="艾森豪矩陣 | Enterprise V6",
    page_icon="🔲",
    layout="wide",
)

AppInitializer.setup()

APP_VERSION = "V6.0 Enterprise Matrix Dashboard"
TODAY = date.today()
Task = Dict[str, Any]


# ============================================================
# Utilities
# ============================================================

def safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    return html.escape(text)


def normalize_people(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    text = str(value).replace("；", ",").replace(";", ",").replace("、", ",")
    return [x.strip() for x in text.split(",") if x.strip()]


def parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text:
        return None

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except ValueError:
            continue

    parsed = pd.to_datetime(text, errors="coerce")
    if pd.notna(parsed):
        return parsed.date()
    return None


def to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def normalize_level(value: Any, default: str = "低") -> str:
    text = str(value or default).strip()
    return "高" if text in {"高", "High", "high", "HIGH", "1", "True", "true", "是", "重要", "緊急"} else "低"


def get_task_title(task: Task) -> str:
    return str(task.get("title") or task.get("任務") or task.get("name") or task.get("task") or "未命名任務")


def get_progress(task: Task) -> int:
    return max(0, min(100, to_int(task.get("progress", 0))))


def get_category(task: Task) -> str:
    return str(task.get("category") or task.get("分類") or "未分類").strip() or "未分類"


def get_due_value(task: Task) -> Any:
    return task.get("due") or task.get("deadline") or task.get("截止日") or task.get("期限") or ""


def task_due_status(task: Task) -> Tuple[str, str, int]:
    due = parse_date(get_due_value(task))
    if not due:
        return "⚪ 未設定期限", "neutral", 999999

    delta = (due - TODAY).days
    if delta < 0:
        return f"🔴 已逾期 {abs(delta)} 天", "danger", delta
    if delta == 0:
        return "🟡 今日截止", "today", delta
    if delta <= 3:
        return f"🟠 即將到期｜剩 {delta} 天", "warning", delta
    return f"🟢 正常｜剩 {delta} 天", "safe", delta


def get_priority_score(task: Task) -> int:
    imp = normalize_level(task.get("importance", "低"))
    urg = normalize_level(task.get("urgency", "低"))
    progress = get_progress(task)
    _, _, due_delta = task_due_status(task)

    score = 0
    if imp == "高":
        score += 50
    if urg == "高":
        score += 40
    if due_delta < 0:
        score += 35 + min(abs(due_delta) * 2, 30)
    elif due_delta == 0:
        score += 25
    elif due_delta <= 3:
        score += 15
    if progress < 30:
        score += 10
    elif progress < 60:
        score += 5
    return score


def get_risk_level(score: int) -> Tuple[str, str]:
    if score >= 100:
        return "Critical", "risk-critical"
    if score >= 75:
        return "High", "risk-high"
    if score >= 45:
        return "Medium", "risk-medium"
    return "Low", "risk-low"


def is_active_task(task: Task) -> bool:
    status = str(task.get("status") or task.get("狀態") or "").strip()
    category = get_category(task)
    return status == "Active" and category != "已完成"


def split_quadrants(tasks: Iterable[Task]) -> Tuple[List[Task], List[Task], List[Task], List[Task]]:
    q1: List[Task] = []
    q2: List[Task] = []
    q3: List[Task] = []
    q4: List[Task] = []

    for task in tasks:
        imp = normalize_level(task.get("importance", "低"))
        urg = normalize_level(task.get("urgency", "低"))
        if imp == "高" and urg == "高":
            q1.append(task)
        elif imp == "高" and urg == "低":
            q2.append(task)
        elif imp == "低" and urg == "高":
            q3.append(task)
        else:
            q4.append(task)
    return q1, q2, q3, q4


def sort_tasks(tasks: List[Task], sort_mode: str) -> List[Task]:
    if sort_mode == "期限最近優先":
        return sorted(tasks, key=lambda t: (task_due_status(t)[2], -get_priority_score(t), get_task_title(t)))
    if sort_mode == "完成度低優先":
        return sorted(tasks, key=lambda t: (get_progress(t), task_due_status(t)[2], get_task_title(t)))
    if sort_mode == "完成度高優先":
        return sorted(tasks, key=lambda t: (-get_progress(t), task_due_status(t)[2], get_task_title(t)))
    if sort_mode == "任務名稱 A-Z":
        return sorted(tasks, key=lambda t: get_task_title(t))
    return sorted(tasks, key=lambda t: (-get_priority_score(t), task_due_status(t)[2], get_task_title(t)))


def filter_tasks(tasks: List[Task]) -> Tuple[List[Task], str]:
    all_people = sorted({p for task in tasks for p in normalize_people(task.get("assignees"))})
    all_categories = sorted({get_category(task) for task in tasks})

    with st.sidebar:
        st.markdown("## 🔎 Matrix Control")
        st.caption("企業版矩陣篩選器")
        keyword = st.text_input("搜尋任務", placeholder="輸入標題 / 指派人 / 分類")
        people = st.multiselect("指派對象", all_people)
        categories = st.multiselect("任務分類", all_categories)
        risk_only = st.toggle("只看逾期 / 3天內到期", value=False)
        sort_mode = st.selectbox(
            "排序方式",
            ["風險分數優先", "期限最近優先", "完成度低優先", "完成度高優先", "任務名稱 A-Z"],
            index=0,
        )
        st.divider()
        st.caption(f"今日：{TODAY.isoformat()}")
        st.caption(APP_VERSION)

    result = tasks
    if keyword:
        key = keyword.strip().lower()
        result = [
            t for t in result
            if key in get_task_title(t).lower()
            or key in get_category(t).lower()
            or any(key in p.lower() for p in normalize_people(t.get("assignees")))
        ]

    if people:
        people_set = set(people)
        result = [t for t in result if people_set.intersection(normalize_people(t.get("assignees")))]

    if categories:
        category_set = set(categories)
        result = [t for t in result if get_category(t) in category_set]

    if risk_only:
        result = [t for t in result if task_due_status(t)[2] <= 3]

    return result, sort_mode


def build_export_df(tasks: List[Task]) -> pd.DataFrame:
    rows = []
    for task in tasks:
        imp = normalize_level(task.get("importance", "低"))
        urg = normalize_level(task.get("urgency", "低"))
        if imp == "高" and urg == "高":
            quadrant = "Q1 重要且緊急"
        elif imp == "高" and urg == "低":
            quadrant = "Q2 重要不緊急"
        elif imp == "低" and urg == "高":
            quadrant = "Q3 緊急不重要"
        else:
            quadrant = "Q4 不重要不緊急"

        due_label, _, due_delta = task_due_status(task)
        score = get_priority_score(task)
        risk_level, _ = get_risk_level(score)
        rows.append({
            "象限": quadrant,
            "任務": get_task_title(task),
            "指派對象": ", ".join(normalize_people(task.get("assignees"))),
            "分類": get_category(task),
            "重要": imp,
            "緊急": urg,
            "期限": get_due_value(task),
            "期限狀態": due_label,
            "剩餘天數": due_delta if due_delta != 999999 else "",
            "完成度": get_progress(task),
            "風險分數": score,
            "風險等級": risk_level,
            "狀態": task.get("status", ""),
        })
    return pd.DataFrame(rows)


# ============================================================
# CSS - Enterprise V6
# ============================================================

st.markdown(
    """
<style>
.block-container { padding-top: .8rem; padding-bottom: 3rem; max-width: 1600px; }
[data-testid="stSidebar"] { background: #f8fafc; border-right: 1px solid #e5e7eb; }

/* Hide Streamlit default top gap visually */
#MainMenu {visibility: hidden;} footer {visibility: hidden;}

.enterprise-shell {
    background: #f8fafc;
    border: 1px solid #e5e7eb;
    border-radius: 26px;
    padding: 18px;
    box-shadow: 0 14px 34px rgba(15, 23, 42, .08);
}

.enterprise-hero {
    position: relative;
    overflow: hidden;
    background: radial-gradient(circle at top right, rgba(96,165,250,.35), transparent 28%),
                linear-gradient(135deg, #0f172a 0%, #172554 48%, #1d4ed8 100%);
    border-radius: 24px;
    padding: 26px 30px;
    margin-bottom: 18px;
    color: white;
    box-shadow: 0 18px 38px rgba(30, 64, 175, .22);
}
.enterprise-hero h1 { margin: 0; font-size: 32px; letter-spacing: .2px; font-weight: 950; }
.enterprise-hero p { margin: 8px 0 0 0; opacity: .92; font-size: 14px; line-height: 1.7; max-width: 980px; }
.hero-row { display:flex; align-items:center; justify-content:space-between; gap:20px; }
.version-pill {
    display:inline-block; padding: 7px 12px; border-radius: 999px;
    background: rgba(255,255,255,.16); font-size: 12px; margin-top: 12px; font-weight: 800;
    border: 1px solid rgba(255,255,255,.22);
}
.today-pill {
    padding: 10px 13px; border-radius: 16px; background: rgba(255,255,255,.12);
    border: 1px solid rgba(255,255,255,.18); font-size: 13px; white-space: nowrap; font-weight: 800;
}

.kpi-card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 18px;
    padding: 16px 18px;
    min-height: 116px;
    box-shadow: 0 8px 22px rgba(15, 23, 42, .07);
    position: relative;
    overflow: hidden;
}
.kpi-card:before { content:""; position:absolute; inset:0 0 auto 0; height:5px; background: #2563eb; }
.kpi-red:before { background:#dc2626; } .kpi-green:before { background:#16a34a; }
.kpi-yellow:before { background:#eab308; } .kpi-blue:before { background:#2563eb; }
.kpi-purple:before { background:#7c3aed; }
.kpi-title { color: #64748b; font-size: 13px; font-weight: 850; }
.kpi-value { color: #0f172a; font-size: 34px; font-weight: 950; line-height: 1.12; margin-top: 6px; }
.kpi-sub { color: #64748b; font-size: 12px; margin-top: 6px; }

.matrix-grid-title {
    display:flex; align-items:center; justify-content:space-between; gap:12px;
    margin: 18px 0 12px 0;
}
.section-title { font-size: 22px; font-weight: 950; color:#0f172a; }
.axis-note { font-size: 12px; color:#64748b; background:white; border:1px solid #e5e7eb; border-radius:999px; padding:6px 11px; }

.matrix-box {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 22px;
    padding: 16px;
    min-height: 600px;
    box-shadow: 0 8px 22px rgba(15, 23, 42, .07);
}
.matrix-q1 { border-top: 9px solid #dc2626; background: linear-gradient(180deg, #fff6f6 0%, #ffffff 100%); }
.matrix-q2 { border-top: 9px solid #16a34a; background: linear-gradient(180deg, #f3fff7 0%, #ffffff 100%); }
.matrix-q3 { border-top: 9px solid #eab308; background: linear-gradient(180deg, #fffbed 0%, #ffffff 100%); }
.matrix-q4 { border-top: 9px solid #2563eb; background: linear-gradient(180deg, #f3f8ff 0%, #ffffff 100%); }
.matrix-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; margin-bottom: 6px; }
.matrix-title { font-size: 20px; font-weight: 950; color: #0f172a; }
.matrix-count { font-size: 13px; font-weight: 900; color: #475569; background: white; border:1px solid #e5e7eb; padding: 4px 10px; border-radius: 999px; }
.matrix-sub { color: #64748b; font-size: 13px; margin-bottom: 14px; line-height: 1.55; }

.task-card {
    background: rgba(255,255,255,.96);
    border: 1px solid #e5e7eb;
    border-left: 6px solid #94a3b8;
    border-radius: 16px;
    padding: 13px 14px 12px 14px;
    margin-bottom: 12px;
    box-shadow: 0 5px 14px rgba(15, 23, 42, .075);
    transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease;
}
.task-card:hover { transform: translateY(-2px); box-shadow: 0 12px 24px rgba(15, 23, 42, .13); border-color: #cbd5e1; }
.task-card.risk-critical { border-left-color:#991b1b; }
.task-card.risk-high { border-left-color:#dc2626; }
.task-card.risk-medium { border-left-color:#f97316; }
.task-card.risk-low { border-left-color:#2563eb; }
.task-topline { display:flex; align-items:flex-start; justify-content:space-between; gap: 10px; }
.task-title { font-size: 15px; font-weight: 950; color: #0f172a; margin-bottom: 8px; line-height:1.35; }
.risk-chip { font-size: 11px; font-weight: 950; padding: 3px 7px; border-radius:999px; white-space:nowrap; }
.risk-critical .risk-chip { background:#fee2e2; color:#991b1b; }
.risk-high .risk-chip { background:#fee2e2; color:#b91c1c; }
.risk-medium .risk-chip { background:#ffedd5; color:#9a3412; }
.risk-low .risk-chip { background:#dbeafe; color:#1d4ed8; }
.task-meta { color: #475569; font-size: 12px; line-height: 1.8; }
.task-footer { display:flex; justify-content:space-between; align-items:center; margin-top: 9px; gap: 8px; flex-wrap: wrap; }
.badge { display:inline-block; padding:4px 9px; border-radius:999px; font-size:12px; font-weight:850; margin:0 4px 5px 0; }
.badge-0 { background:#dbeafe; color:#1d4ed8; } .badge-1 { background:#dcfce7; color:#166534; }
.badge-2 { background:#ffedd5; color:#9a3412; } .badge-3 { background:#f3e8ff; color:#6b21a8; }
.badge-4 { background:#e0e7ff; color:#3730a3; }
.status-pill { display:inline-block; padding:4px 9px; border-radius:999px; font-size:12px; font-weight:900; }
.status-danger { background:#fee2e2; color:#b91c1c; }
.status-today { background:#fef3c7; color:#92400e; }
.status-warning { background:#ffedd5; color:#9a3412; }
.status-safe { background:#dcfce7; color:#166534; }
.status-neutral { background:#e5e7eb; color:#475569; }
.progress-line { display:flex; align-items:center; gap:8px; margin-top: 8px; }
.progress-bar-wrap { flex:1; background:#e5e7eb; border-radius:999px; height:9px; overflow:hidden; }
.progress-bar { background: linear-gradient(90deg, #2563eb, #60a5fa); height:9px; border-radius:999px; }
.progress-text { color:#334155; font-size:12px; font-weight:900; min-width: 38px; text-align:right; }
.empty-box { background: rgba(255,255,255,.74); border:1px dashed #cbd5e1; border-radius: 15px; padding: 22px; color:#64748b; text-align:center; }

.insight-panel {
    background: white; border:1px solid #e5e7eb; border-radius: 22px;
    padding: 16px; box-shadow: 0 8px 22px rgba(15, 23, 42, .07);
    margin-bottom: 14px;
}
.insight-title { font-size: 17px; font-weight: 950; color:#0f172a; margin-bottom: 12px; }
.insight-item { border:1px solid #e5e7eb; border-radius: 14px; padding:10px 11px; margin-bottom:9px; background:#f8fafc; }
.insight-name { color:#0f172a; font-weight:900; font-size:13px; line-height:1.45; }
.insight-meta { color:#64748b; font-size:12px; margin-top:4px; }
.risk-alert { background:#fff7ed; border:1px solid #fed7aa; border-left:6px solid #f97316; border-radius:16px; padding:12px 14px; color:#9a3412; margin: 8px 0 16px 0; }
.export-box { background:white; border:1px solid #e5e7eb; border-radius:20px; padding:16px; box-shadow: 0 8px 22px rgba(15, 23, 42, .07); }

@media (max-width: 900px) {
    .hero-row { flex-direction: column; align-items:flex-start; }
    .today-pill { white-space: normal; }
    .matrix-box { min-height: auto; }
}
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# Data Loading
# ============================================================

raw_tasks = st.session_state.get("tasks", [])
if raw_tasks is None:
    raw_tasks = []

if not isinstance(raw_tasks, list):
    st.error("任務資料格式異常：st.session_state.tasks 不是 list。請檢查 AppInitializer.setup() 或 Google Sheet 載入邏輯。")
    st.stop()

active_tasks = [task for task in raw_tasks if isinstance(task, dict) and is_active_task(task)]
filtered_tasks, sort_mode = filter_tasks(active_tasks)
filtered_tasks = sort_tasks(filtered_tasks, sort_mode)
q1, q2, q3, q4 = split_quadrants(filtered_tasks)
q1, q2, q3, q4 = [sort_tasks(q, sort_mode) for q in (q1, q2, q3, q4)]

risk_tasks = [task for task in filtered_tasks if task_due_status(task)[2] <= 3]
overdue_tasks = [task for task in filtered_tasks if task_due_status(task)[2] < 0]
today_tasks = [task for task in filtered_tasks if task_due_status(task)[2] == 0]
completed_avg = round(sum(get_progress(t) for t in filtered_tasks) / len(filtered_tasks), 1) if filtered_tasks else 0
high_risk_tasks = [task for task in filtered_tasks if get_priority_score(task) >= 75]


# ============================================================
# Header
# ============================================================

st.markdown('<div class="enterprise-shell">', unsafe_allow_html=True)
st.markdown(
    f"""
<div class="enterprise-hero">
    <div class="hero-row">
        <div>
            <h1>🔲 艾森豪矩陣</h1>
            <p>工程任務優先級控管中心｜用「重要性 × 緊急性」快速判斷立即處理、排程規劃、授權交辦與降載項目。</p>
            <span class="version-pill">{APP_VERSION}</span>
        </div>
        <div class="today-pill">📅 今日：{TODAY.isoformat()}</div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

if len(active_tasks) == 0:
    st.info("目前沒有 Active 任務可顯示。")

if risk_tasks:
    st.markdown(
        f"""
<div class="risk-alert">
    ⚠️ 目前篩選結果有 <b>{len(risk_tasks)}</b> 筆任務已逾期或 3 天內到期；其中逾期 <b>{len(overdue_tasks)}</b> 筆、今日截止 <b>{len(today_tasks)}</b> 筆。
</div>
""",
        unsafe_allow_html=True,
    )


# ============================================================
# KPI Cards
# ============================================================

k1, k2, k3, k4, k5, k6 = st.columns(6)
kpis = [
    (k1, "全部任務", len(filtered_tasks), "目前篩選結果", "kpi-blue"),
    (k2, "逾期", len(overdue_tasks), "需立即追蹤", "kpi-red"),
    (k3, "今日截止", len(today_tasks), "今日需處理", "kpi-yellow"),
    (k4, "高風險", len(high_risk_tasks), "Risk ≥ 75", "kpi-purple"),
    (k5, "平均完成", f"{completed_avg}%", "任務推進率", "kpi-green"),
    (k6, "Q1 任務", len(q1), "重要且緊急", "kpi-red"),
]

for col, title, value, sub, css in kpis:
    with col:
        st.markdown(
            f"""
<div class="kpi-card {css}">
    <div class="kpi-title">{safe_text(title)}</div>
    <div class="kpi-value">{safe_text(value)}</div>
    <div class="kpi-sub">{safe_text(sub)}</div>
</div>
""",
            unsafe_allow_html=True,
        )


# ============================================================
# Render HTML Components
# ============================================================

def build_task_card_html(task: Task) -> str:
    title = safe_text(get_task_title(task), "未命名任務")
    category = safe_text(get_category(task), "未分類")
    due_raw = get_due_value(task)
    due = safe_text(due_raw, "未設定")
    progress = get_progress(task)
    due_label, due_class, _ = task_due_status(task)
    score = get_priority_score(task)
    risk_level, risk_css = get_risk_level(score)

    people = normalize_people(task.get("assignees"))
    if people:
        badges = "".join(
            f'<span class="badge badge-{idx % 5}">👤 {safe_text(person)}</span>'
            for idx, person in enumerate(people)
        )
    else:
        badges = '<span class="badge badge-0">👤 未指派</span>'

    description = safe_text(task.get("description") or task.get("notes") or task.get("備註") or "")
    desc_html = f'<div class="task-meta">📝 {description}</div>' if description else ""

    return f"""
<div class="task-card {risk_css}">
    <div class="task-topline">
        <div class="task-title">📌 {title}</div>
        <span class="risk-chip">{safe_text(risk_level)}｜{score}</span>
    </div>
    <div>{badges}</div>
    <div class="task-meta">🏷️ {category}　｜　📅 {due}</div>
    {desc_html}
    <div class="progress-line">
        <div class="progress-bar-wrap"><div class="progress-bar" style="width:{progress}%;"></div></div>
        <div class="progress-text">{progress}%</div>
    </div>
    <div class="task-footer">
        <span class="status-pill status-{due_class}">{safe_text(due_label)}</span>
        <span class="task-meta">風險分數 {score}</span>
    </div>
</div>
"""


def render_quadrant(css_class: str, icon: str, title: str, subtitle: str, tasks: List[Task]) -> None:
    cards_html = "".join(build_task_card_html(task) for task in tasks)
    if not cards_html:
        cards_html = '<div class="empty-box">目前沒有任務</div>'

    st.markdown(
        f"""
<div class="matrix-box {css_class}">
    <div class="matrix-header">
        <div>
            <div class="matrix-title">{safe_text(icon)} {safe_text(title)}</div>
            <div class="matrix-sub">{safe_text(subtitle)}</div>
        </div>
        <div class="matrix-count">{len(tasks)} Tasks</div>
    </div>
    {cards_html}
</div>
""",
        unsafe_allow_html=True,
    )


def insight_item_html(task: Task) -> str:
    title = safe_text(get_task_title(task), "未命名任務")
    due_label, _, _ = task_due_status(task)
    people = ", ".join(normalize_people(task.get("assignees"))) or "未指派"
    score = get_priority_score(task)
    return f"""
<div class="insight-item">
    <div class="insight-name">{title}</div>
    <div class="insight-meta">{safe_text(due_label)}｜Risk {score}｜{safe_text(people)}</div>
</div>
"""


def render_insight_panel(title: str, tasks: List[Task], empty_text: str) -> None:
    body = "".join(insight_item_html(task) for task in tasks[:5])
    if not body:
        body = f'<div class="empty-box">{safe_text(empty_text)}</div>'
    st.markdown(
        f"""
<div class="insight-panel">
    <div class="insight-title">{safe_text(title)}</div>
    {body}
</div>
""",
        unsafe_allow_html=True,
    )


# ============================================================
# Enterprise Matrix + Insight Panel
# ============================================================

st.markdown(
    """
<div class="matrix-grid-title">
    <div class="section-title">📌 Priority Matrix</div>
    <div class="axis-note">重要 ↑ ｜ 緊急 ← → 不緊急</div>
</div>
""",
    unsafe_allow_html=True,
)

matrix_area, insight_area = st.columns([3.4, 1.05], gap="large")

with matrix_area:
    row1_left, row1_right = st.columns(2, gap="large")
    with row1_left:
        render_quadrant("matrix-q1", "🔥", "第一象限", "重要且緊急｜立即處理、主管追蹤、優先排除阻塞", q1)
    with row1_right:
        render_quadrant("matrix-q2", "📅", "第二象限", "重要但不緊急｜排程規劃、預防性改善、專案推進", q2)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    row2_left, row2_right = st.columns(2, gap="large")
    with row2_left:
        render_quadrant("matrix-q3", "🤝", "第三象限", "緊急但不重要｜授權交辦、標準化處理、避免打斷核心工作", q3)
    with row2_right:
        render_quadrant("matrix-q4", "⚪", "第四象限", "不重要且不緊急｜降低投入、暫緩、合併或取消", q4)

with insight_area:
    top_risk = sort_tasks(filtered_tasks, "風險分數優先")
    due_soon = sort_tasks([t for t in filtered_tasks if task_due_status(t)[2] <= 3], "期限最近優先")
    low_progress = sort_tasks([t for t in filtered_tasks if get_progress(t) < 50], "完成度低優先")
    render_insight_panel("🚨 Top Risk", top_risk, "目前沒有風險任務")
    render_insight_panel("📅 Due Soon", due_soon, "3 天內沒有到期任務")
    render_insight_panel("📉 Low Progress", low_progress, "沒有低完成度任務")


# ============================================================
# Export / Management View
# ============================================================

st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
st.markdown('<div class="export-box">', unsafe_allow_html=True)
st.subheader("📊 管理檢視與匯出")
export_df = build_export_df(filtered_tasks)

left_export, right_export = st.columns([2.2, 1])
with left_export:
    st.dataframe(export_df, use_container_width=True, hide_index=True)
with right_export:
    csv = export_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="⬇️ 下載矩陣任務 CSV",
        data=csv,
        file_name=f"eisenhower_matrix_{TODAY.isoformat()}.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.caption("匯出內容會依照目前側邊欄篩選結果產生。")

st.caption(f"最後檢視日期：{TODAY.isoformat()}｜{APP_VERSION}")
st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)
