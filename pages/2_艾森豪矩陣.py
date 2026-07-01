# -*- coding: utf-8 -*-
"""
pages/2_艾森豪矩陣.py
Enterprise Matrix Dashboard V5.0

設計目標：
- 保留既有 StreamFlow / utils 架構
- 強化企業任務管理視覺化、篩選、風險提醒、排序與匯出
- 避免 Google Sheet 重複讀取；優先使用 AppInitializer 已載入的 st.session_state.tasks
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
    page_title="艾森豪矩陣 | Enterprise Matrix",
    page_icon="🔲",
    layout="wide",
)

AppInitializer.setup()

APP_VERSION = "V5.0 Enterprise Matrix Dashboard"
TODAY = date.today()


# ============================================================
# Utilities
# ============================================================

Task = Dict[str, Any]


def safe_text(value: Any, default: str = "") -> str:
    """HTML escape for safe markdown rendering."""
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    return html.escape(text)


def normalize_people(value: Any) -> List[str]:
    """Normalize assignees from list/string into clean list."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    text = str(value).replace("；", ",").replace(";", ",").replace("、", ",")
    return [x.strip() for x in text.split(",") if x.strip()]


def parse_date(value: Any) -> date | None:
    """Parse common date formats from task due field."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text:
        return None

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except ValueError:
            continue

    try:
        parsed = pd.to_datetime(text, errors="coerce")
        if pd.notna(parsed):
            return parsed.date()
    except Exception:
        return None
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
    return "高" if text in {"高", "High", "high", "HIGH", "1", "True", "true", "是"} else "低"


def task_due_status(task: Task) -> Tuple[str, str, int]:
    """Return status label, css class, days delta."""
    due = parse_date(task.get("due") or task.get("deadline") or task.get("截止日"))
    if not due:
        return "未設定期限", "neutral", 999999

    delta = (due - TODAY).days
    if delta < 0:
        return f"逾期 {abs(delta)} 天", "danger", delta
    if delta == 0:
        return "今日到期", "warning", delta
    if delta <= 3:
        return f"{delta} 天內到期", "warning", delta
    return f"剩 {delta} 天", "safe", delta


def get_task_title(task: Task) -> str:
    return str(task.get("title") or task.get("任務") or task.get("name") or "未命名任務")


def get_progress(task: Task) -> int:
    return max(0, min(100, to_int(task.get("progress", 0))))


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
        score += 30
    elif due_delta == 0:
        score += 20
    elif due_delta <= 3:
        score += 10
    if progress < 30:
        score += 5
    return score


def is_active_task(task: Task) -> bool:
    status = str(task.get("status") or task.get("狀態") or "").strip()
    category = str(task.get("category") or task.get("分類") or "").strip()
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
    return sorted(tasks, key=lambda t: (-get_priority_score(t), task_due_status(t)[2], get_task_title(t)))


def filter_tasks(tasks: List[Task]) -> Tuple[List[Task], str]:
    all_people = sorted({p for task in tasks for p in normalize_people(task.get("assignees"))})
    all_categories = sorted({str(task.get("category", "")).strip() for task in tasks if str(task.get("category", "")).strip()})

    with st.sidebar:
        st.markdown("### 🔎 矩陣篩選")
        keyword = st.text_input("搜尋任務", placeholder="輸入標題 / 指派人 / 分類")
        people = st.multiselect("指派對象", all_people)
        categories = st.multiselect("任務分類", all_categories)
        risk_only = st.toggle("只看逾期 / 3天內到期", value=False)
        sort_mode = st.selectbox(
            "排序方式",
            ["風險分數優先", "期限最近優先", "完成度低優先", "完成度高優先"],
            index=0,
        )

    result = tasks

    if keyword:
        key = keyword.strip().lower()
        result = [
            t for t in result
            if key in get_task_title(t).lower()
            or key in str(t.get("category", "")).lower()
            or any(key in p.lower() for p in normalize_people(t.get("assignees")))
        ]

    if people:
        people_set = set(people)
        result = [t for t in result if people_set.intersection(normalize_people(t.get("assignees")))]

    if categories:
        category_set = set(categories)
        result = [t for t in result if str(t.get("category", "")).strip() in category_set]

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
        rows.append({
            "象限": quadrant,
            "任務": get_task_title(task),
            "指派對象": ", ".join(normalize_people(task.get("assignees"))),
            "分類": task.get("category", ""),
            "重要": imp,
            "緊急": urg,
            "期限": task.get("due", ""),
            "期限狀態": due_label,
            "剩餘天數": due_delta if due_delta != 999999 else "",
            "完成度": get_progress(task),
            "風險分數": get_priority_score(task),
            "狀態": task.get("status", ""),
        })
    return pd.DataFrame(rows)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
<style>
.block-container { padding-top: 1rem; padding-bottom: 3rem; }
[data-testid="stSidebar"] { background: #f8fafc; }

.enterprise-hero {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 58%, #2563eb 100%);
    border-radius: 22px;
    padding: 24px 28px;
    margin-bottom: 18px;
    color: white;
    box-shadow: 0 12px 32px rgba(15, 23, 42, .22);
}
.enterprise-hero h1 { margin: 0; font-size: 30px; }
.enterprise-hero p { margin: 8px 0 0 0; opacity: .9; }
.version-pill {
    display:inline-block; padding: 5px 11px; border-radius: 999px;
    background: rgba(255,255,255,.16); font-size: 12px; margin-top: 10px;
}

.kpi-card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 18px;
    padding: 16px 18px;
    min-height: 118px;
    box-shadow: 0 6px 18px rgba(15, 23, 42, .08);
}
.kpi-title { color: #64748b; font-size: 13px; font-weight: 700; }
.kpi-value { color: #0f172a; font-size: 34px; font-weight: 900; line-height: 1.15; }
.kpi-sub { color: #64748b; font-size: 12px; margin-top: 5px; }

.matrix-box {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 20px;
    padding: 16px;
    min-height: 580px;
    box-shadow: 0 6px 18px rgba(15, 23, 42, .08);
}
.matrix-q1 { border-top: 9px solid #dc2626; background: #fff7f7; }
.matrix-q2 { border-top: 9px solid #16a34a; background: #f5fff7; }
.matrix-q3 { border-top: 9px solid #eab308; background: #fffdf1; }
.matrix-q4 { border-top: 9px solid #2563eb; background: #f4f8ff; }
.matrix-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; }
.matrix-title { font-size: 20px; font-weight: 900; color: #0f172a; }
.matrix-count { font-size: 13px; font-weight: 800; color: #475569; background: white; border:1px solid #e5e7eb; padding: 3px 9px; border-radius: 999px; }
.matrix-sub { color: #64748b; font-size: 13px; margin-bottom: 14px; }

.task-card {
    background: rgba(255,255,255,.92);
    border: 1px solid #e5e7eb;
    border-left: 6px solid #94a3b8;
    border-radius: 15px;
    padding: 13px 14px;
    margin-bottom: 12px;
    box-shadow: 0 4px 12px rgba(15, 23, 42, .07);
}
.task-card:hover { transform: translateY(-1px); transition: .15s ease; box-shadow: 0 8px 20px rgba(15, 23, 42, .11); }
.task-title { font-size: 15px; font-weight: 900; color: #0f172a; margin-bottom: 8px; }
.task-meta { color: #475569; font-size: 12px; line-height: 1.8; }
.task-footer { display:flex; justify-content:space-between; align-items:center; margin-top: 9px; gap: 8px; }
.badge { display:inline-block; padding:3px 8px; border-radius:999px; background:#e0ecff; color:#1d4ed8; font-size:12px; font-weight:700; margin:0 4px 4px 0; }
.status-pill { display:inline-block; padding:3px 8px; border-radius:999px; font-size:12px; font-weight:800; }
.status-danger { background:#fee2e2; color:#b91c1c; }
.status-warning { background:#fef3c7; color:#92400e; }
.status-safe { background:#dcfce7; color:#166534; }
.status-neutral { background:#e5e7eb; color:#475569; }
.progress-bar-wrap { background:#e5e7eb; border-radius:999px; height:8px; overflow:hidden; margin-top:6px; }
.progress-bar { background:#2563eb; height:8px; border-radius:999px; }
.empty-box { background: rgba(255,255,255,.65); border:1px dashed #cbd5e1; border-radius: 14px; padding: 18px; color:#64748b; text-align:center; }
.risk-alert { background:#fff7ed; border:1px solid #fed7aa; border-left:6px solid #f97316; border-radius:14px; padding:12px 14px; color:#9a3412; margin: 6px 0 18px 0; }
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

active_tasks = [task for task in raw_tasks if isinstance(task, dict) and is_active_task(task)]
filtered_tasks, sort_mode = filter_tasks(active_tasks)
filtered_tasks = sort_tasks(filtered_tasks, sort_mode)

q1, q2, q3, q4 = split_quadrants(filtered_tasks)
q1, q2, q3, q4 = [sort_tasks(q, sort_mode) for q in (q1, q2, q3, q4)]

risk_tasks = [task for task in filtered_tasks if task_due_status(task)[2] <= 3]
overdue_tasks = [task for task in filtered_tasks if task_due_status(task)[2] < 0]
completed_avg = round(sum(get_progress(t) for t in filtered_tasks) / len(filtered_tasks), 1) if filtered_tasks else 0


# ============================================================
# Header
# ============================================================

st.markdown(
    f"""
<div class="enterprise-hero">
    <h1>🔲 艾森豪矩陣</h1>
    <p>以「重要性 × 緊急性」控管工程任務優先級，協助主管快速判斷立即處理、排程、交辦與降載項目。</p>
    <span class="version-pill">{APP_VERSION}</span>
</div>
""",
    unsafe_allow_html=True,
)

if not isinstance(raw_tasks, list):
    st.error("任務資料格式異常：st.session_state.tasks 不是 list。請檢查 AppInitializer.setup() 或 Google Sheet 載入邏輯。")
    st.stop()

if len(active_tasks) == 0:
    st.info("目前沒有 Active 任務可顯示。")

if risk_tasks:
    st.markdown(
        f"""
<div class="risk-alert">
    ⚠️ 目前篩選結果中有 <b>{len(risk_tasks)}</b> 筆任務已逾期或 3 天內到期，其中逾期 <b>{len(overdue_tasks)}</b> 筆。建議先處理第一象限與逾期任務。
</div>
""",
        unsafe_allow_html=True,
    )


# ============================================================
# KPI Cards
# ============================================================

k1, k2, k3, k4, k5, k6 = st.columns(6)

kpis = [
    (k1, "全部任務", len(filtered_tasks), "目前篩選後任務"),
    (k2, "🔥 Q1", len(q1), "重要且緊急"),
    (k3, "📅 Q2", len(q2), "重要不緊急"),
    (k4, "🤝 Q3", len(q3), "緊急不重要"),
    (k5, "🔵 Q4", len(q4), "低優先降載"),
    (k6, "平均完成", f"{completed_avg}%", "任務推進率"),
]

for col, title, value, sub in kpis:
    with col:
        st.markdown(
            f"""
<div class="kpi-card">
    <div class="kpi-title">{safe_text(title)}</div>
    <div class="kpi-value">{safe_text(value)}</div>
    <div class="kpi-sub">{safe_text(sub)}</div>
</div>
""",
            unsafe_allow_html=True,
        )

st.markdown("---")


# ============================================================
# Render Components
# ============================================================


def render_task_card(task: Task) -> None:
    title = safe_text(get_task_title(task), "未命名任務")
    category = safe_text(task.get("category", "未分類"), "未分類")
    due = safe_text(task.get("due", "未設定"), "未設定")
    progress = get_progress(task)
    due_label, due_class, _ = task_due_status(task)
    score = get_priority_score(task)

    people = normalize_people(task.get("assignees"))
    badges = "".join(f'<span class="badge">👤 {safe_text(p)}</span>' for p in people) or '<span class="badge">未指派</span>'

    owner_line = badges
    description = safe_text(task.get("description") or task.get("notes") or task.get("備註") or "")
    desc_html = f"<div class='task-meta'>📝 {description}</div>" if description else ""

    st.markdown(
        f"""
<div class="task-card">
    <div class="task-title">📌 {title}</div>
    <div>{owner_line}</div>
    <div class="task-meta">🏷️ 分類：{category}</div>
    <div class="task-meta">📅 期限：{due}</div>
    {desc_html}
    <div class="progress-bar-wrap"><div class="progress-bar" style="width:{progress}%;"></div></div>
    <div class="task-footer">
        <span class="status-pill status-{due_class}">{safe_text(due_label)}</span>
        <span class="task-meta">完成度 {progress}%｜風險 {score}</span>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_quadrant(css_class: str, icon: str, title: str, subtitle: str, tasks: List[Task]) -> None:
    st.markdown(
        f"""
<div class="matrix-box {css_class}">
    <div class="matrix-header">
        <div class="matrix-title">{safe_text(icon)} {safe_text(title)}</div>
        <div class="matrix-count">{len(tasks)} 件</div>
    </div>
    <div class="matrix-sub">{safe_text(subtitle)}</div>
""",
        unsafe_allow_html=True,
    )

    if not tasks:
        st.markdown("<div class='empty-box'>目前沒有任務</div>", unsafe_allow_html=True)
    else:
        for task in tasks:
            render_task_card(task)

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# Enterprise Matrix Layout
# ============================================================

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
    render_quadrant("matrix-q4", "🔵", "第四象限", "不重要且不緊急｜降低投入、暫緩、合併或取消", q4)


# ============================================================
# Export / Management View
# ============================================================

st.markdown("---")
st.subheader("📊 管理檢視與匯出")

export_df = build_export_df(filtered_tasks)

left_export, right_export = st.columns([2, 1])
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
