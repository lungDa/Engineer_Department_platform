import html
from datetime import date, datetime

import streamlit as st
from utils import ViewComponents, TaskService, StreamFlowEngine as engine
from utils import AppInitializer, UserService


# =========================================================
# V3.6 Enterprise Ultimate Dashboard
# 任務看板 / Kanban Board
# =========================================================

st.set_page_config(page_title="任務看板｜V3.6 Enterprise Ultimate Dashboard", layout="wide")
st.header("📋 任務看板")
st.caption("V3.6 Enterprise Ultimate Dashboard｜任務發布、指派人員、工作量、進度與風險總覽")

AppInitializer.setup()


# =========================================================
# UI Style
# =========================================================
st.markdown(
    """
    <style>
    .v36-dashboard-card {
        border: 1px solid rgba(148, 163, 184, 0.25);
        border-radius: 16px;
        padding: 14px 16px;
        background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
        margin-bottom: 12px;
    }
    .v36-title {
        font-size: 1.03rem;
        font-weight: 800;
        margin-bottom: 8px;
        line-height: 1.35;
    }
    .v36-chip {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 4px 9px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 700;
        margin: 3px 4px 3px 0;
        border: 1px solid rgba(148, 163, 184, 0.25);
        background: rgba(30, 41, 59, 0.08);
    }
    .v36-assignee {
        background: rgba(37, 99, 235, 0.14);
        color: #2563eb;
        border-color: rgba(37, 99, 235, 0.28);
    }
    .v36-assignee-more {
        background: rgba(100, 116, 139, 0.14);
        color: #64748b;
        border-color: rgba(100, 116, 139, 0.28);
    }
    .v36-priority-high {
        background: rgba(239, 68, 68, 0.14);
        color: #dc2626;
        border-color: rgba(239, 68, 68, 0.28);
    }
    .v36-priority-medium {
        background: rgba(245, 158, 11, 0.14);
        color: #d97706;
        border-color: rgba(245, 158, 11, 0.28);
    }
    .v36-priority-low {
        background: rgba(34, 197, 94, 0.14);
        color: #16a34a;
        border-color: rgba(34, 197, 94, 0.28);
    }
    .v36-risk-overdue {
        background: rgba(239, 68, 68, 0.14);
        color: #dc2626;
        border-color: rgba(239, 68, 68, 0.28);
    }
    .v36-risk-soon {
        background: rgba(245, 158, 11, 0.14);
        color: #d97706;
        border-color: rgba(245, 158, 11, 0.28);
    }
    .v36-risk-normal {
        background: rgba(34, 197, 94, 0.14);
        color: #16a34a;
        border-color: rgba(34, 197, 94, 0.28);
    }
    .v36-meta {
        color: #64748b;
        font-size: 12px;
        margin-top: 6px;
        margin-bottom: 6px;
    }
    .v36-section-title {
        font-weight: 800;
        margin: 10px 0 4px 0;
        color: #334155;
    }
    .v36-mini-bar-wrap {
        width: 100%;
        height: 8px;
        border-radius: 999px;
        background: rgba(148, 163, 184, 0.20);
        overflow: hidden;
        margin-top: 8px;
    }
    .v36-mini-bar {
        height: 8px;
        border-radius: 999px;
        background: linear-gradient(90deg, #2563eb, #22c55e);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# Helper Functions
# =========================================================
def _safe_text(value, default=""):
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _escape(value):
    return html.escape(_safe_text(value))


def _parse_assignees(value):
    """相容 list / tuple / set / comma string / semicolon string."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        raw = str(value).replace("；", ",").replace(";", ",").replace("、", ",")
        raw_items = raw.split(",")
    result = []
    for item in raw_items:
        name = str(item).strip()
        if name and name not in result:
            result.append(name)
    return result


def _parse_tags(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        raw = str(value).replace("；", ",").replace(";", ",").replace("、", ",")
        raw_items = raw.split(",")
    return [str(x).strip() for x in raw_items if str(x).strip()]


def _parse_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _safe_text(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%Y.%m.%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except Exception:
            pass
    try:
        return datetime.fromisoformat(text[:10]).date()
    except Exception:
        return None


def _days_left(due_value):
    due_date = _parse_date(due_value)
    if due_date is None:
        return None
    return (due_date - date.today()).days


def _risk_chip(days_left, progress):
    if progress >= 100:
        return '<span class="v36-chip v36-risk-normal">✅ 已完成</span>'
    if days_left is None:
        return '<span class="v36-chip v36-assignee-more">🗓️ 未設定日期</span>'
    if days_left < 0:
        return f'<span class="v36-chip v36-risk-overdue">🚨 逾期 {abs(days_left)} 天</span>'
    if days_left <= 3:
        return f'<span class="v36-chip v36-risk-soon">⚠️ 剩 {days_left} 天</span>'
    return f'<span class="v36-chip v36-risk-normal">⏳ 剩 {days_left} 天</span>'


def _priority_text(task):
    imp = _safe_text(task.get("importance"), "低")
    urg = _safe_text(task.get("urgency"), "低")
    if imp == "高" and urg == "高":
        return "High", "v36-priority-high", "🔥"
    if imp == "高" or urg == "高":
        return "Medium", "v36-priority-medium", "⚡"
    return "Low", "v36-priority-low", "🟢"


def _render_assignee_chips(assignees, max_visible=4):
    if not assignees:
        return '<span class="v36-chip v36-assignee-more">👤 未指派</span>'

    chips = []
    full_list = "、".join(assignees)
    for name in assignees[:max_visible]:
        safe_name = _escape(name)
        initial = safe_name[0] if safe_name else "?"
        chips.append(
            f'<span class="v36-chip v36-assignee" title="{html.escape(full_list)}">👤 {initial}｜{safe_name}</span>'
        )
    if len(assignees) > max_visible:
        chips.append(
            f'<span class="v36-chip v36-assignee-more" title="{html.escape(full_list)}">+{len(assignees) - max_visible}</span>'
        )
    return "".join(chips)


def _render_tag_chips(tags, max_visible=4):
    if not tags:
        return ""
    chips = []
    for tag in tags[:max_visible]:
        chips.append(f'<span class="v36-chip">🏷️ {_escape(tag)}</span>')
    if len(tags) > max_visible:
        chips.append(f'<span class="v36-chip v36-assignee-more">+{len(tags) - max_visible}</span>')
    return "".join(chips)


def _task_progress(task):
    try:
        return max(0, min(100, int(float(task.get("progress", 0)))))
    except Exception:
        return 0


def _render_task_card(task, category_index, is_locked, locked_by):
    title = _escape(task.get("title", "未命名任務"))
    progress = _task_progress(task)
    assignees = _parse_assignees(task.get("assignees"))
    tags = _parse_tags(task.get("tags"))
    days = _days_left(task.get("due"))
    priority_label, priority_class, priority_icon = _priority_text(task)
    locked_icon = "🔒" if is_locked else "📌"

    assignee_html = _render_assignee_chips(assignees)
    tag_html = _render_tag_chips(tags)
    risk_html = _risk_chip(days, progress)
    due_text = _escape(task.get("due", "未設定"))
    hours = _escape(task.get("hours_spent", 0))

    card_html = f"""
    <div class="v36-dashboard-card">
        <div class="v36-title">{locked_icon} {title}</div>
        <div>{assignee_html}</div>
        <div class="v36-meta">📅 {due_text}　|　⏱️ 累計工時：{hours} h</div>
        <div>
            <span class="v36-chip {priority_class}">{priority_icon} {priority_label}</span>
            {risk_html}
        </div>
        <div class="v36-mini-bar-wrap">
            <div class="v36-mini-bar" style="width:{progress}%;"></div>
        </div>
        <div class="v36-meta">📊 完成度：{progress}%</div>
        <div>{tag_html}</div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

    if is_locked:
        st.error(f"等待前置：{', '.join(locked_by)}")

    with st.expander("📝 詳細設定與回報"):
        st.markdown("**👥 指派人員**")
        if assignees:
            st.info("、".join(assignees))
        else:
            st.warning("此任務尚未指定人員。")

        new_imp = st.selectbox(
            "重要度",
            ["高", "低"],
            index=0 if task.get("importance") == "高" else 1,
            key=f"imp_{task['id']}",
        )

        new_urg = st.selectbox(
            "緊急度",
            ["高", "低"],
            index=0 if task.get("urgency") == "高" else 1,
            key=f"urg_{task['id']}",
        )

        task["importance"] = new_imp
        task["urgency"] = new_urg

        new_prog = st.slider(
            "完成進度 (%)",
            0,
            100,
            progress,
            key=f"prog_{task['id']}",
        )

        if new_prog != task.get("progress"):
            task["progress"] = new_prog
            engine.add_log(task, f"將進度更新為 {new_prog}%")

        add_h = st.number_input(
            "➕ 新增本次花費工時",
            min_value=0.0,
            step=0.5,
            key=f"add_h_{task['id']}",
        )

        if st.button("紀錄工時", key=f"btn_h_{task['id']}") and add_h > 0:
            task["hours_spent"] = task.get("hours_spent", 0) + add_h
            engine.add_log(task, f"紀錄了 {add_h} 小時，總計 {task['hours_spent']} 小時")
            st.rerun()

        task["notes"] = st.text_area(
            "備註",
            value=task.get("notes", ""),
            key=f"note_{task['id']}",
        )

        st.markdown("**📜 活動軌跡**")
        with st.container(height=100):
            for log in reversed(task.get("history", [])):
                st.caption(log)

    new_status = st.selectbox(
        "變更狀態",
        st.session_state.categories,
        index=category_index,
        key=f"move_{task['id']}",
        disabled=is_locked,
    )

    if new_status != task["category"] and not is_locked:
        engine.add_log(task, f"將狀態從「{task['category']}」移至「{new_status}」")
        task["category"] = new_status
        st.rerun()


# =========================================================
# Quick Create Task
# =========================================================
with st.expander("📝 快速建立任務", expanded=False):
    with st.form("task_board_quick_add_task_form", clear_on_submit=True):
        publisher_account = st.text_input("發布人工號 / 帳號")
        publisher_password = st.text_input("發布人密碼", type="password")
        t_title = st.text_input("任務名稱")

        c1, c2, c3 = st.columns([1.2, 1.2, 2])
        with c1:
            t_cat = st.selectbox("分類", st.session_state.categories)
        with c2:
            t_due = st.date_input("排程日期", st.session_state.selected_date)
        with c3:
            t_assign = st.multiselect("👥 指派", UserService.get_partner_names())

        if t_assign:
            st.info("👥 本次將指派給：\n\n" + "\n".join(f"• {name}" for name in t_assign))
        else:
            st.warning("尚未指定任何人。")

        c4, c5 = st.columns(2)
        with c4:
            t_imp = st.selectbox("重要度", ["高", "低"])
        with c5:
            t_urg = st.selectbox("緊急度", ["高", "低"])

        submitted = st.form_submit_button("建立任務", width="stretch")
        if submitted:
            if not publisher_account.strip() or not publisher_password:
                st.warning("請輸入發布人的工號與密碼。")
            elif not t_title.strip():
                st.warning("請輸入任務名稱。")
            elif not t_assign:
                st.warning("請至少指定一位人員。")
            else:
                ok, msg, publisher = UserService.authenticate(publisher_account, publisher_password)
                if not ok:
                    st.error(msg)
                else:
                    author = publisher.get("name") or publisher.get("account") or publisher_account
                    account = publisher.get("account") or publisher_account
                    new_t = {
                        "title": t_title,
                        "category": t_cat,
                        "due": t_due,
                        "assignees": t_assign,
                        "status": "Active",
                        "progress": 0,
                        "hours_spent": 0.0,
                        "importance": t_imp,
                        "urgency": t_urg,
                        "tags": "",
                        "notes": "",
                        "depends_on": [],
                        "history": [],
                    }
                    engine.add_log(new_t, "透過任務看板快速建立任務", author=author)
                    try:
                        TaskService.add_task(new_t, author=author, account=account)
                        st.success(f"任務已建立並寫入 Google Sheet。發布人：{author}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"任務寫入 Google Sheet 失敗：{e}")
                        if st.session_state.get("sheet_db_error"):
                            with st.expander("Google Sheet 寫入錯誤詳情", expanded=False):
                                st.code(str(st.session_state.get("sheet_db_error")), language="text")


# =========================================================
# Dashboard KPI
# =========================================================
tasks = st.session_state.get("tasks", [])
total_tasks = len(tasks)
completed_tasks = sum(1 for t in tasks if _task_progress(t) >= 100)
active_tasks = max(total_tasks - completed_tasks, 0)
overdue_tasks = sum(1 for t in tasks if (_days_left(t.get("due")) is not None and _days_left(t.get("due")) < 0 and _task_progress(t) < 100))
avg_progress = round(sum(_task_progress(t) for t in tasks) / total_tasks, 1) if total_tasks else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("總任務", total_tasks)
k2.metric("進行中", active_tasks)
k3.metric("已完成", completed_tasks)
k4.metric("逾期", overdue_tasks)
k5.metric("平均進度", f"{avg_progress}%")

# =========================================================
# Workload Dashboard
# =========================================================
with st.expander("👥 人員工作量總覽", expanded=False):
    workload = {}
    for task in tasks:
        for person in _parse_assignees(task.get("assignees")):
            workload.setdefault(person, {"total": 0, "active": 0, "overdue": 0})
            workload[person]["total"] += 1
            if _task_progress(task) < 100:
                workload[person]["active"] += 1
            days = _days_left(task.get("due"))
            if days is not None and days < 0 and _task_progress(task) < 100:
                workload[person]["overdue"] += 1

    if workload:
        rows = []
        for person, data in sorted(workload.items(), key=lambda item: item[1]["active"], reverse=True):
            rows.append(
                {
                    "人員": person,
                    "總任務": data["total"],
                    "進行中": data["active"],
                    "逾期": data["overdue"],
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("目前沒有可統計的指派資料。")


# =========================================================
# Advanced Filters
# =========================================================
f_assignees, f_tags = ViewComponents.render_filters()

with st.expander("🛠️ 看板設定（新增分類）"):
    new_cat = st.text_input("自訂新分類/欄位名稱")

    if st.button("建立欄位") and new_cat and new_cat not in st.session_state.categories:
        st.session_state.categories.append(new_cat)
        st.rerun()


# =========================================================
# Kanban Board
# =========================================================
categories = st.session_state.get("categories", [])
if not categories:
    st.warning("尚未設定任何看板分類。")
    st.stop()

cols = st.columns(len(categories))

for idx, col in enumerate(cols):
    cat_name = categories[idx]

    with col:
        raw_cat_tasks = [t for t in tasks if t.get("category") == cat_name]
        cat_tasks = TaskService.get_filtered_tasks(f_assignees, f_tags, raw_cat_tasks)

        done_count = sum(1 for t in cat_tasks if _task_progress(t) >= 100)
        overdue_count = sum(
            1
            for t in cat_tasks
            if (_days_left(t.get("due")) is not None and _days_left(t.get("due")) < 0 and _task_progress(t) < 100)
        )

        st.markdown(f"#### 📁 {cat_name}")
        st.caption(f"{len(cat_tasks)} 件｜完成 {done_count} 件｜逾期 {overdue_count} 件")
        st.divider()

        if not cat_tasks:
            st.info("此欄位目前沒有任務。")
            continue

        # 企業版排序：逾期 > 高優先 > 日期近 > 其他
        def sort_key(task):
            days = _days_left(task.get("due"))
            priority_label, _, _ = _priority_text(task)
            priority_rank = {"High": 0, "Medium": 1, "Low": 2}.get(priority_label, 3)
            overdue_rank = 0 if days is not None and days < 0 and _task_progress(task) < 100 else 1
            day_rank = days if days is not None else 9999
            return (overdue_rank, priority_rank, day_rank)

        for t in sorted(cat_tasks, key=sort_key):
            is_locked, locked_by = TaskService.is_task_locked(t)
            _render_task_card(t, idx, is_locked, locked_by)
