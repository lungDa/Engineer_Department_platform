# -*- coding: utf-8 -*-
"""
pages/2_艾森豪矩陣.py
Enterprise Matrix Dashboard V8 Fixed Quadrant Scroll

修正重點：
- 任務卡改用 Streamlit 原生元件 + st.progress，避免 HTML 片段外露
- 不再用「開啟 div 後穿插 Streamlit 元件」的寫法
- 保留企業版：搜尋、篩選、排序、KPI、風險判斷、CSV 匯出、右側洞察
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Tuple

import pandas as pd
import streamlit as st
from utils import AppInitializer


# ============================================================
# Page Config / Init
# ============================================================

st.set_page_config(
    page_title="艾森豪矩陣",
    page_icon="🔲",
    layout="wide",
)

AppInitializer.setup()

APP_VERSION = "V8.2 Fixed Matrix & Insight Scroll"
TODAY = date.today()
Task = Dict[str, Any]

# 每張任務卡固定 172px，三張卡＋間距剛好放入 536px 捲動區。
# 因此畫面會精準呈現 3 張完整任務卡，第 4 張起需滾動查看。
QUADRANT_TASK_VIEW_HEIGHT = 536


# ============================================================
# Utilities
# ============================================================

def text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    s = str(value).strip()
    return s if s else default


def normalize_people(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    s = str(value).replace("；", ",").replace(";", ",").replace("、", ",")
    return [x.strip() for x in s.split(",") if x.strip()]


def parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    s = str(value).strip()
    if not s:
        return None

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(s[:19], fmt).date()
        except ValueError:
            pass

    parsed = pd.to_datetime(s, errors="coerce")
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
    s = str(value or default).strip()
    return "高" if s in {"高", "High", "high", "HIGH", "1", "True", "true", "是", "重要", "緊急"} else "低"


def get_task_title(task: Task) -> str:
    return text(task.get("title") or task.get("任務") or task.get("name") or task.get("task"), "未命名任務")


def get_progress(task: Task) -> int:
    return max(0, min(100, to_int(task.get("progress", 0))))


def get_category(task: Task) -> str:
    return text(task.get("category") or task.get("分類"), "未分類")


def get_due_value(task: Task) -> Any:
    return task.get("due") or task.get("deadline") or task.get("截止日") or task.get("期限") or ""


def task_due_status(task: Task) -> Tuple[str, str, int]:
    due = parse_date(get_due_value(task))
    if not due:
        return "⚪ 未設定期限", "gray", 999999

    delta = (due - TODAY).days
    if delta < 0:
        return f"🔴 已逾期 {abs(delta)} 天", "red", delta
    if delta == 0:
        return "🟡 今日截止", "orange", delta
    if delta <= 3:
        return f"🟠 即將到期｜剩 {delta} 天", "orange", delta
    return f"🟢 正常｜剩 {delta} 天", "green", delta


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


def get_risk_level(score: int) -> str:
    if score >= 100:
        return "Critical"
    if score >= 75:
        return "High"
    if score >= 45:
        return "Medium"
    return "Low"


def is_active_task(task: Task) -> bool:
    status = text(task.get("status") or task.get("狀態"))
    return status == "Active" and get_category(task) != "已完成"


def split_quadrants(tasks: Iterable[Task]) -> Tuple[List[Task], List[Task], List[Task], List[Task]]:
    q1, q2, q3, q4 = [], [], [], []
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
            "風險等級": get_risk_level(score),
            "狀態": task.get("status", ""),
        })
    return pd.DataFrame(rows)


def badge_people(people: List[str]) -> str:
    if not people:
        return "👤 未指派"
    return "　".join([f"👤 {p}" for p in people])


# ============================================================
# CSS：只做外觀，不包住 Streamlit 元件，避免 HTML 外露
# ============================================================

st.markdown(
    """
<style>
:root{
    --bg-main:#0F172A;
    --bg-sidebar:#111827;
    --bg-card:#1E293B;
    --bg-card-2:#111827;
    --border:#334155;
    --text-main:#F8FAFC;
    --text-muted:#CBD5E1;
    --text-soft:#94A3B8;
    --blue:#2563EB;
    --green:#16A34A;
    --orange:#F59E0B;
    --red:#DC2626;
    --purple:#8B5CF6;
}

/* Page / Sidebar */
.stApp, section.main, .main, .main .block-container{
    background:var(--bg-main) !important;
    color:var(--text-main) !important;
}
.block-container{
    padding-top:.8rem;
    padding-bottom:3rem;
    max-width:1600px;
}
[data-testid="stSidebar"],
[data-testid="stSidebarContent"]{
    background:var(--bg-sidebar) !important;
    color:var(--text-main) !important;
    border-right:1px solid #1f2937;
}
#MainMenu{visibility:hidden;} footer{visibility:hidden;}

/* Text */
h1,h2,h3,h4,h5,h6,p,label,span,div{
    color:var(--text-main) !important;
}
small, .stCaption, [data-testid="stCaptionContainer"], .small-muted{
    color:var(--text-soft) !important;
}

/* Header */
.enterprise-hero{
    background:linear-gradient(135deg,#020617 0%,#111827 42%,#1E3A8A 100%);
    border:1px solid var(--border);
    border-radius:24px;
    padding:26px 30px;
    margin-bottom:18px;
    color:white;
    box-shadow:0 18px 44px rgba(0,0,0,.45);
}
.enterprise-hero h1{margin:0;font-size:32px;font-weight:950;color:#fff !important;}
.enterprise-hero p{margin:8px 0 0 0;color:var(--text-muted) !important;font-size:14px;line-height:1.7;}
.version-pill{
    display:inline-block;
    padding:7px 12px;
    border-radius:999px;
    background:rgba(37,99,235,.24);
    font-size:12px;
    margin-top:12px;
    font-weight:800;
    border:1px solid rgba(96,165,250,.35);
    color:#DBEAFE !important;
}

/* KPI Cards - Dark Enterprise */
.kpi-wrap{
    background:linear-gradient(180deg,#1E293B 0%,#111827 100%) !important;
    border:1px solid var(--border) !important;
    border-radius:18px;
    padding:16px 18px;
    min-height:112px;
    box-shadow:0 10px 26px rgba(0,0,0,.38);
    transition:all .22s ease;
    position:relative;
    overflow:hidden;
}
.kpi-wrap::before{
    content:"";
    position:absolute;
    inset:0 auto 0 0;
    width:6px;
    background:var(--blue);
    opacity:.95;
}
.kpi-wrap:hover{
    transform:translateY(-3px);
    box-shadow:0 16px 34px rgba(0,0,0,.50);
    border-color:#475569 !important;
}
.kpi-title{
    color:var(--text-muted) !important;
    font-size:13px;
    font-weight:850;
    letter-spacing:.02em;
    padding-left:4px;
}
.kpi-value{
    color:#FFFFFF !important;
    font-size:34px;
    font-weight:950;
    line-height:1.12;
    margin-top:8px;
    padding-left:4px;
}
.kpi-sub{
    color:var(--text-soft) !important;
    font-size:12px;
    margin-top:8px;
    padding-left:4px;
}

/* KPI accent colors by order */
div[data-testid="column"]:nth-of-type(1) .kpi-wrap::before{background:var(--blue);}
div[data-testid="column"]:nth-of-type(2) .kpi-wrap::before{background:var(--red);}
div[data-testid="column"]:nth-of-type(3) .kpi-wrap::before{background:var(--orange);}
div[data-testid="column"]:nth-of-type(4) .kpi-wrap::before{background:var(--purple);}
div[data-testid="column"]:nth-of-type(5) .kpi-wrap::before{background:var(--green);}
div[data-testid="column"]:nth-of-type(6) .kpi-wrap::before{background:#38BDF8;}

/* Streamlit containers / cards */
div[data-testid="stVerticalBlockBorderWrapper"]{
    background:var(--bg-card) !important;
    border:1px solid var(--border) !important;
    border-radius:18px !important;
    box-shadow:0 8px 24px rgba(0,0,0,.34);
}
[data-testid="column"]{background:transparent !important;}

.quadrant-title{font-size:20px;font-weight:950;color:#FFFFFF !important;}
.quadrant-sub{color:var(--text-soft) !important;font-size:13px;line-height:1.55;margin-bottom:8px;}
.task-mini-title{font-size:16px;font-weight:900;color:#FFFFFF !important;}
.task-meta{color:var(--text-muted) !important;font-size:13px;line-height:1.8;}

/* 固定四象限：標題不動，只有任務卡清單捲動。 */
.matrix-quadrant{
    height:670px;
    box-sizing:border-box;
    background:linear-gradient(180deg,#1E293B 0%,#111827 100%);
    border:1px solid var(--border);
    border-radius:18px;
    padding:16px;
    box-shadow:0 8px 24px rgba(0,0,0,.34);
    overflow:hidden;
    margin-bottom:18px;
}
.matrix-quadrant-head{
    height:92px;
    box-sizing:border-box;
    border-bottom:1px solid #334155;
    margin-bottom:10px;
}
.matrix-quadrant-title-row{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:10px;
}
.matrix-quadrant-count{
    flex:none;
    border-radius:999px;
    background:#1D4ED8;
    border:1px solid #3B82F6;
    padding:4px 9px;
    color:#FFF !important;
    font-size:12px;
    font-weight:800;
}
.matrix-task-scroll{
    height:536px;
    overflow-y:auto;
    overflow-x:hidden;
    padding-right:7px;
    scroll-behavior:smooth;
    scrollbar-color:#475569 #111827;
    scrollbar-width:thin;
}
.matrix-task-scroll::-webkit-scrollbar{width:8px;}
.matrix-task-scroll::-webkit-scrollbar-thumb{background:#475569;border-radius:999px;}
.matrix-task-scroll::-webkit-scrollbar-track{background:#111827;border-radius:999px;}
.matrix-task-card{
    height:172px;
    box-sizing:border-box;
    background:#0F172A;
    border:1px solid #334155;
    border-radius:14px;
    padding:12px 13px;
    margin-bottom:10px;
    overflow:hidden;
}
.matrix-task-card:last-child{margin-bottom:0;}
.matrix-task-title{
    height:23px;
    overflow:hidden;
    white-space:nowrap;
    text-overflow:ellipsis;
    font-size:15px;
    font-weight:900;
    color:#FFF !important;
}
.matrix-task-line{
    height:22px;
    overflow:hidden;
    white-space:nowrap;
    text-overflow:ellipsis;
    color:#CBD5E1 !important;
    font-size:12px;
    line-height:22px;
}
.matrix-task-badges{height:26px;overflow:hidden;white-space:nowrap;}
.matrix-badge{
    display:inline-block;
    padding:3px 7px;
    margin:2px 4px 2px 0;
    border-radius:999px;
    background:#1E3A8A;
    border:1px solid #2563EB;
    color:#DBEAFE !important;
    font-size:11px;
    font-weight:800;
}
.matrix-badge.red{background:#450A0A;border-color:#DC2626;color:#FECACA !important;}
.matrix-badge.orange{background:#451A03;border-color:#F59E0B;color:#FDE68A !important;}
.matrix-badge.green{background:#052E16;border-color:#16A34A;color:#BBF7D0 !important;}
.matrix-progress-track{height:7px;background:#334155;border-radius:999px;overflow:hidden;margin-top:6px;}
.matrix-progress-fill{height:7px;background:linear-gradient(90deg,#2563EB,#22C55E);border-radius:999px;}
.matrix-empty{
    height:172px;
    display:flex;
    align-items:center;
    justify-content:center;
    border:1px dashed #475569;
    border-radius:14px;
    color:#94A3B8 !important;
    font-weight:800;
}

/* 右側洞察面板：標題固定、精準顯示三張、其餘滾動。 */
.insight-panel{
    height:402px;
    box-sizing:border-box;
    background:linear-gradient(180deg,#1E293B 0%,#111827 100%);
    border:1px solid var(--border);
    border-radius:18px;
    padding:13px;
    box-shadow:0 8px 24px rgba(0,0,0,.34);
    overflow:hidden;
    margin-bottom:18px;
}
.insight-head{
    height:42px;
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:8px;
    border-bottom:1px solid #334155;
    margin-bottom:8px;
    font-size:16px;
    font-weight:900;
    color:#FFF !important;
}
.insight-count{
    flex:none;
    padding:3px 7px;
    border-radius:999px;
    background:#1D4ED8;
    border:1px solid #3B82F6;
    color:#FFF !important;
    font-size:11px;
    font-weight:800;
}
.insight-scroll{
    height:326px;
    overflow-y:auto;
    overflow-x:hidden;
    padding-right:6px;
    scrollbar-color:#475569 #111827;
    scrollbar-width:thin;
}
.insight-scroll::-webkit-scrollbar{width:7px;}
.insight-scroll::-webkit-scrollbar-thumb{background:#475569;border-radius:999px;}
.insight-scroll::-webkit-scrollbar-track{background:#111827;border-radius:999px;}
.insight-card{
    height:102px;
    box-sizing:border-box;
    background:#0F172A;
    border:1px solid #334155;
    border-radius:12px;
    padding:9px 10px;
    margin-bottom:10px;
    overflow:hidden;
}
.insight-card:last-child{margin-bottom:0;}
.insight-task-title{
    height:22px;
    overflow:hidden;
    white-space:nowrap;
    text-overflow:ellipsis;
    font-size:13px;
    font-weight:900;
    color:#FFF !important;
}
.insight-task-meta{
    height:21px;
    overflow:hidden;
    white-space:nowrap;
    text-overflow:ellipsis;
    font-size:11px;
    line-height:21px;
    color:#CBD5E1 !important;
}
.insight-empty{
    height:102px;
    display:flex;
    align-items:center;
    justify-content:center;
    border:1px dashed #475569;
    border-radius:12px;
    color:#94A3B8 !important;
    font-size:12px;
    font-weight:800;
    text-align:center;
}

/* Inputs */
.stTextInput input,
.stTextArea textarea,
.stSelectbox div[data-baseweb="select"],
.stMultiSelect div[data-baseweb="select"]{
    background:#0B1220 !important;
    color:var(--text-main) !important;
    border:1px solid var(--border) !important;
    border-radius:10px !important;
}

/* Buttons */
.stButton>button,
.stDownloadButton>button{
    background:var(--blue) !important;
    color:#FFF !important;
    border:none !important;
    border-radius:10px !important;
    font-weight:800 !important;
}
.stButton>button:hover,
.stDownloadButton>button:hover{
    background:#1D4ED8 !important;
    transform:translateY(-1px);
}

/* Alerts */
[data-testid="stAlert"]{
    background:#111827 !important;
    border:1px solid var(--border) !important;
    color:var(--text-main) !important;
}

/* Dataframe */
[data-testid="stDataFrame"]{
    background:var(--bg-card) !important;
    border:1px solid var(--border) !important;
    border-radius:14px !important;
}

hr{border-color:var(--border) !important;}
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

st.markdown(
    f"""
<div class="enterprise-hero">
    <h1>🔲 艾森豪矩陣</h1>
    <p>工程任務優先級控管中心｜用「重要性 × 緊急性」快速判斷立即處理、排程規劃、授權交辦與降載項目。</p>
    <span class="version-pill">{APP_VERSION}｜今日：{TODAY.isoformat()}</span>
</div>
""",
    unsafe_allow_html=True,
)

if len(active_tasks) == 0:
    st.info("目前沒有 Active 任務可顯示。")

if risk_tasks:
    st.warning(f"目前篩選結果有 {len(risk_tasks)} 筆任務已逾期或 3 天內到期；其中逾期 {len(overdue_tasks)} 筆、今日截止 {len(today_tasks)} 筆。")


# ============================================================
# KPI Cards
# ============================================================

def render_kpi(title: str, value: Any, sub: str) -> None:
    st.markdown(
        f"""
<div class="kpi-wrap">
    <div class="kpi-title">{title}</div>
    <div class="kpi-value">{value}</div>
    <div class="kpi-sub">{sub}</div>
</div>
""",
        unsafe_allow_html=True,
    )

k1, k2, k3, k4, k5, k6 = st.columns(6)
with k1: render_kpi("全部任務", len(filtered_tasks), "目前篩選結果")
with k2: render_kpi("逾期", len(overdue_tasks), "需立即追蹤")
with k3: render_kpi("今日截止", len(today_tasks), "今日需處理")
with k4: render_kpi("高風險", len(high_risk_tasks), "Risk ≥ 75")
with k5: render_kpi("平均完成", f"{completed_avg}%", "任務推進率")
with k6: render_kpi("Q1 任務", len(q1), "重要且緊急")

st.divider()


# ============================================================
# Native Render Components：避免 HTML 片段外露
# ============================================================

def render_task_card(task: Task) -> None:
    title = get_task_title(task)
    category = get_category(task)
    due = text(get_due_value(task), "未設定")
    progress = get_progress(task)
    due_label, color, _ = task_due_status(task)
    score = get_priority_score(task)
    risk_level = get_risk_level(score)
    people = normalize_people(task.get("assignees"))
    description = text(task.get("description") or task.get("notes") or task.get("備註"))

    with st.container(border=True):
        top_l, top_r = st.columns([4, 1])
        with top_l:
            st.markdown(f"<div class='task-mini-title'>📌 {title}</div>", unsafe_allow_html=True)
        with top_r:
            st.badge(f"{risk_level}｜{score}", color="red" if score >= 75 else "orange" if score >= 45 else "blue")

        st.markdown(f"<div class='task-meta'>{badge_people(people)}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='task-meta'>🏷️ {category}　｜　📅 {due}</div>", unsafe_allow_html=True)
        if description:
            st.caption(f"📝 {description}")

        st.progress(progress, text=f"完成度 {progress}%")

        foot_l, foot_r = st.columns([2, 1])
        with foot_l:
            st.badge(due_label, color=color)
        with foot_r:
            st.caption(f"風險分數 {score}")


def render_quadrant(icon: str, title: str, subtitle: str, tasks: List[Task]) -> None:
    cards = []
    for task in tasks:
        task_title = html.escape(get_task_title(task))
        category = html.escape(get_category(task))
        due = html.escape(text(get_due_value(task), "未設定"))
        progress = get_progress(task)
        due_label, due_color, _ = task_due_status(task)
        score = get_priority_score(task)
        risk_level = get_risk_level(score)
        people = normalize_people(task.get("assignees"))
        people_text = html.escape("、".join(people) if people else "未指派")
        description = text(task.get("description") or task.get("notes") or task.get("備註"), "無備註")
        description = html.escape(description[:55] + ("…" if len(description) > 55 else ""))
        color_class = due_color if due_color in {"red", "orange", "green"} else ""

        cards.append(
            f"""
            <div class="matrix-task-card" title="{task_title}">
                <div class="matrix-task-title">📌 {task_title}</div>
                <div class="matrix-task-line">👤 {people_text}</div>
                <div class="matrix-task-line">🏷️ {category}　｜　📅 {due}</div>
                <div class="matrix-task-line">📝 {description}</div>
                <div class="matrix-task-badges">
                    <span class="matrix-badge {color_class}">{html.escape(due_label)}</span>
                    <span class="matrix-badge">{risk_level}｜Risk {score}</span>
                </div>
                <div class="matrix-progress-track">
                    <div class="matrix-progress-fill" style="width:{progress}%"></div>
                </div>
            </div>
            """
        )

    task_content = "".join(cards) if cards else '<div class="matrix-empty">目前沒有任務</div>'
    st.markdown(
        f"""
        <div class="matrix-quadrant">
            <div class="matrix-quadrant-head">
                <div class="matrix-quadrant-title-row">
                    <div class="quadrant-title">{icon} {html.escape(title)}</div>
                    <div class="matrix-quadrant-count">{len(tasks)} Tasks</div>
                </div>
                <div class="quadrant-sub">{html.escape(subtitle)}</div>
            </div>
            <div class="matrix-task-scroll">{task_content}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_insight_panel(title: str, tasks: List[Task], empty_text: str) -> None:
    cards = []
    for task in tasks:
        task_title = html.escape(get_task_title(task))
        score = get_priority_score(task)
        due_label, due_color, _ = task_due_status(task)
        people = html.escape("、".join(normalize_people(task.get("assignees"))) or "未指派")
        progress = get_progress(task)
        color_class = due_color if due_color in {"red", "orange", "green"} else ""
        cards.append(
            f"""
            <div class="insight-card" title="{task_title}">
                <div class="insight-task-title">📌 {task_title}</div>
                <div class="insight-task-meta">👤 {people}</div>
                <div class="insight-task-meta">{html.escape(due_label)}</div>
                <div class="matrix-task-badges">
                    <span class="matrix-badge {color_class}">Risk {score}</span>
                    <span class="matrix-badge">進度 {progress}%</span>
                </div>
            </div>
            """
        )

    task_content = "".join(cards) if cards else f'<div class="insight-empty">{html.escape(empty_text)}</div>'
    st.markdown(
        f"""
        <div class="insight-panel">
            <div class="insight-head">
                <span>{html.escape(title)}</span>
                <span class="insight-count">{len(tasks)}</span>
            </div>
            <div class="insight-scroll">{task_content}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# Enterprise Matrix + Insight Panel
# ============================================================

st.markdown("### 📌 Priority Matrix")
st.caption("重要 ↑ ｜緊急 ← → 不緊急")

matrix_area, insight_area = st.columns([3.4, 1.05], gap="large")

with matrix_area:
    row1_left, row1_right = st.columns(2, gap="large")
    with row1_left:
        render_quadrant("🔥", "第一象限", "重要且緊急｜立即處理、主管追蹤、優先排除阻塞", q1)
    with row1_right:
        render_quadrant("📅", "第二象限", "重要但不緊急｜排程規劃、預防性改善、專案推進", q2)

    row2_left, row2_right = st.columns(2, gap="large")
    with row2_left:
        render_quadrant("🤝", "第三象限", "緊急但不重要｜授權交辦、標準化處理、避免打斷核心工作", q3)
    with row2_right:
        render_quadrant("⚪", "第四象限", "不重要且不緊急｜降低投入、暫緩、合併或取消", q4)

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

st.divider()
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
