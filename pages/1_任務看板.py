import html
from datetime import date, datetime

import pandas as pd
import streamlit as st
from config.功能開關 import 要求功能開啟

from utils import (
    AppInitializer,
    SheetDB,
    TaskService,
    UserService,
    assignee_departments,
    current_department,
    encode_departments,
    parse_date,
    parse_float,
    parse_int,
)
from services.notification_service import notification_service
from services.task_checklist import (
    checklist_progress,
    create_checklist_item,
    normalize_checklist,
)
from services.task_activity import TaskActivityService
from services.task_attachment import TaskAttachmentService


st.set_page_config(page_title="任務看板｜Enterprise V6", layout="wide")
要求功能開啟("任務看板")
AppInitializer.setup(load_tasks=True, load_meetings=False, load_approvals=False)

STATUS_ORDER = ["待辦事項", "進行中", "已完成"]
TODAY = date.today()


def clean_list(value):
    if isinstance(value, (list, tuple, set)):
        values = value
    elif value in (None, ""):
        return []
    else:
        values = str(value).replace("；", ",").replace(";", ",").replace("、", ",").split(",")
    result = []
    for item in values:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result


def task_progress(task):
    return checklist_progress(task.get("checklist"), parse_int(task.get("progress", 0), 0))


def task_due(task):
    return parse_date(task.get("due"), TODAY)


def is_completed(task):
    return task_progress(task) >= 100 or str(task.get("category", "")) == "已完成"


def is_overdue(task):
    return not is_completed(task) and task_due(task) < TODAY


def risk_label(task):
    if is_completed(task):
        return "✅ 已完成", "ok"
    days = (task_due(task) - TODAY).days
    if days < 0:
        return f"🚨 逾期 {abs(days)} 天", "danger"
    if days == 0:
        return "⚠️ 今日截止", "warning"
    if days <= 3:
        return f"⚠️ 剩 {days} 天", "warning"
    return f"⏳ 剩 {days} 天", "ok"


def priority_score(task):
    score = 0
    if str(task.get("importance", "低")) == "高":
        score += 2
    if str(task.get("urgency", "低")) == "高":
        score += 2
    if is_overdue(task):
        score += 5
    return score


def persist_task(task, changes, account, password):
    ok, message, editor = UserService.authenticate(account, password)
    if not ok:
        raise PermissionError(message)
    editor_name = editor.get("name") or editor.get("account") or account
    TaskService.update_task(task.get("id"), changes, author=editor_name, account=account)
    return editor_name


def show_notification_result(result):
    channels = (result.get("data") or {}).get("channels", {})
    labels = {"teams": "Teams", "outlook": "Outlook", "line": "LINE"}
    for channel, channel_result in channels.items():
        label = labels.get(channel, channel)
        message = channel_result.get("message", "")
        if channel_result.get("skipped"):
            st.info(f"{label}：略過（{message}）")
        elif channel_result.get("ok"):
            st.success(f"{label}：成功")
        else:
            st.warning(f"{label}：失敗（{message}）")


pending_notification = st.session_state.pop("task_notification_result", None)
if pending_notification:
    st.markdown("##### 🔔 上次任務通知結果")
    show_notification_result(pending_notification)


st.markdown(
    """
    <style>
    .task-card {border:1px solid rgba(148,163,184,.28);border-radius:16px;padding:14px 15px;
      background:linear-gradient(180deg,rgba(255,255,255,.06),rgba(255,255,255,.02));
      box-shadow:0 8px 24px rgba(15,23,42,.12);margin-bottom:10px}
    .task-title {font-size:1.02rem;font-weight:800;line-height:1.35;margin-bottom:8px}
    .task-meta {font-size:.82rem;color:#94a3b8;margin:5px 0}
    .chip {display:inline-block;border-radius:999px;padding:3px 8px;margin:2px 3px 2px 0;
      font-size:.75rem;font-weight:700;background:rgba(59,130,246,.14);border:1px solid rgba(59,130,246,.28)}
    .chip.danger {background:rgba(239,68,68,.14);border-color:rgba(239,68,68,.30);color:#ef4444}
    .chip.warning {background:rgba(245,158,11,.14);border-color:rgba(245,158,11,.30);color:#f59e0b}
    .chip.ok {background:rgba(34,197,94,.14);border-color:rgba(34,197,94,.30);color:#22c55e}
    .progress-bg {height:8px;border-radius:99px;background:rgba(148,163,184,.22);overflow:hidden;margin-top:9px}
    .progress-fg {height:8px;border-radius:99px;background:linear-gradient(90deg,#2563eb,#22c55e)}
    </style>
    """,
    unsafe_allow_html=True,
)

title_col, refresh_col = st.columns([8, 1])
with title_col:
    st.header("📋 任務看板｜Enterprise V6")
    st.caption(f"目前部門：{current_department()}｜任務新增、進度回報、風險與人員負載整合管理")
with refresh_col:
    st.write("")
    if st.button("🔄 重新整理", width="stretch"):
        SheetDB.clear_cache("Tasks")
        st.session_state.tasks = TaskService.load_by_department(current_department())
        st.rerun()

tasks = [task for task in st.session_state.get("tasks", []) if task.get("status", "Active") == "Active"]
partner_names = UserService.get_all_partner_names(current_department())


# =========================================================
# 新增任務
# =========================================================
with st.expander("➕ 新增任務", expanded=False):
    if not partner_names:
        st.warning("目前沒有啟用中的人員名單。請先在人員名單新增人員。")

    st.caption(f"目前部門「{current_department()}」的人員會排在最上方，其餘部門人員也可選擇。")
    pick_col, dept_col, all_col, clear_col = st.columns([2.4, 1, 1, 1])
    with pick_col:
        quick_department = st.selectbox("快速選取部門", UserService.get_departments(), key="task_quick_department")
    with dept_col:
        st.write("")
        if st.button("選取該部門全員", key="task_select_department", width="stretch"):
            selected = st.session_state.get("enterprise_task_assignees", [])
            dept_names = UserService.get_partner_names_by_department(quick_department)
            st.session_state.enterprise_task_assignees = list(dict.fromkeys(selected + dept_names))
            st.rerun()
    with all_col:
        st.write("")
        if st.button("選取所有人", key="task_select_all", width="stretch"):
            st.session_state.enterprise_task_assignees = partner_names
            st.rerun()
    with clear_col:
        st.write("")
        if st.button("清除選取", key="task_clear_all", width="stretch"):
            st.session_state.enterprise_task_assignees = []
            st.rerun()

    with st.form("enterprise_add_task", clear_on_submit=True):
        auth1, auth2 = st.columns(2)
        with auth1:
            creator_account = st.text_input("建立人帳號／工號")
        with auth2:
            creator_password = st.text_input("建立人密碼", type="password")

        title = st.text_input("任務名稱")
        c1, c2, c3 = st.columns([1.1, 1.1, 2])
        with c1:
            category = st.selectbox("任務狀態", STATUS_ORDER[:-1])
        with c2:
            due = st.date_input("截止日期", TODAY)
        with c3:
            assignees = st.multiselect("指派人員（可跨部門）", partner_names, key="enterprise_task_assignees")

        p1, p2, p3 = st.columns(3)
        with p1:
            importance = st.selectbox("重要度", ["高", "低"], index=1)
        with p2:
            urgency = st.selectbox("緊急度", ["高", "低"], index=1)
        with p3:
            estimated_tags = st.text_input("標籤", placeholder="設計, 採購, 現場")
        notes = st.text_area("任務說明／備註")
        initial_checklist = st.text_area(
            "初始子項目（選填，每行一項）",
            placeholder="IO List 確認\n電氣圖繪製\nPLC 程式\nFAT 測試",
            help="建立後可再為每個子項目設定負責人與期限。",
        )
        notify_channels = st.multiselect(
            "建立後通知管道",
            ["Teams", "Outlook", "LINE"],
            default=["Teams", "Outlook", "LINE"],
            help="Outlook 寄給已設定公司 Email 的指派人員；LINE 廣播給官方帳號好友。",
        )

        submitted = st.form_submit_button("建立任務", width="stretch")
        if submitted:
            if not creator_account.strip() or not creator_password:
                st.error("請輸入建立人的帳號與密碼。")
            elif not title.strip():
                st.error("請輸入任務名稱。")
            elif not assignees:
                st.error("請至少指派一位人員。")
            else:
                ok, message, creator = UserService.authenticate(creator_account, creator_password)
                if not ok:
                    st.error(message)
                else:
                    creator_name = creator.get("name") or creator_account
                    new_task = {
                        "title": title.strip(), "category": category, "due": due,
                        "assignees": assignees, "status": "Active", "progress": 0,
                        "hours_spent": 0.0,
                        "department": encode_departments(
                            assignee_departments(assignees),
                            fallback=current_department(),
                        ),
                        "importance": importance, "urgency": urgency,
                        "tags": ",".join(clean_list(estimated_tags)), "notes": notes.strip(),
                        "depends_on": [],
                        "checklist": [
                            {
                                "id": index,
                                "title": line.strip(),
                                "completed": False,
                                "assignee": "",
                                "due": "",
                            }
                            for index, line in enumerate(initial_checklist.splitlines(), start=1)
                            if line.strip()
                        ],
                        "history": [f"[{datetime.now().strftime('%m-%d %H:%M')}] {creator_name} 建立任務"],
                    }
                    try:
                        created_task = TaskService.add_task(new_task, author=creator_name, account=creator.get("account", creator_account))
                        task_for_notification = created_task if isinstance(created_task, dict) else new_task
                        result = notification_service.send_task_event(
                            event="created",
                            task=task_for_notification,
                            actor=creator_name,
                            channels=[channel.lower() for channel in notify_channels],
                        )
                        st.session_state["task_notification_result"] = result
                        SheetDB.clear_cache("Tasks")
                        st.success("任務已建立並寫入 Google Sheet。")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"任務建立失敗：{exc}")


# =========================================================
# KPI
# =========================================================
total = len(tasks)
completed = sum(is_completed(task) for task in tasks)
overdue = sum(is_overdue(task) for task in tasks)
in_progress = sum(str(task.get("category")) == "進行中" and not is_completed(task) for task in tasks)
average = round(sum(task_progress(task) for task in tasks) / total, 1) if total else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("部門任務", total)
k2.metric("進行中", in_progress)
k3.metric("已完成", completed)
k4.metric("逾期", overdue)
k5.metric("平均進度", f"{average}%")


# =========================================================
# 篩選與負載
# =========================================================
with st.expander("🔍 篩選與人員負載", expanded=False):
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        keyword = st.text_input("搜尋", placeholder="任務、備註、標籤")
    with f2:
        selected_people = st.multiselect("指派人員", partner_names)
    with f3:
        selected_priority = st.multiselect("重要／緊急", ["重要", "緊急", "重要且緊急"])
    with f4:
        risk_filter = st.selectbox("期限風險", ["全部", "逾期", "3 天內", "未完成", "已完成"])

    workload = []
    for person in partner_names:
        owned = [task for task in tasks if person in clean_list(task.get("assignees"))]
        workload.append({
            "人員": person,
            "全部任務": len(owned),
            "未完成": sum(not is_completed(task) for task in owned),
            "逾期": sum(is_overdue(task) for task in owned),
            "平均進度": f"{round(sum(task_progress(task) for task in owned) / len(owned), 1) if owned else 0}%",
        })
    if workload:
        st.dataframe(pd.DataFrame(workload), width="stretch", hide_index=True)


def matches_filters(task):
    if keyword.strip():
        haystack = " ".join([
            str(task.get("title", "")), str(task.get("notes", "")),
            str(task.get("tags", "")), " ".join(clean_list(task.get("assignees"))),
        ]).lower()
        if keyword.strip().lower() not in haystack:
            return False
    if selected_people and not set(selected_people).intersection(clean_list(task.get("assignees"))):
        return False
    imp = str(task.get("importance", "低")) == "高"
    urg = str(task.get("urgency", "低")) == "高"
    if selected_priority:
        flags = set()
        if imp:
            flags.add("重要")
        if urg:
            flags.add("緊急")
        if imp and urg:
            flags.add("重要且緊急")
        if not flags.intersection(selected_priority):
            return False
    days = (task_due(task) - TODAY).days
    if risk_filter == "逾期" and not is_overdue(task):
        return False
    if risk_filter == "3 天內" and not (not is_completed(task) and 0 <= days <= 3):
        return False
    if risk_filter == "未完成" and is_completed(task):
        return False
    if risk_filter == "已完成" and not is_completed(task):
        return False
    return True


filtered_tasks = [task for task in tasks if matches_filters(task)]


def render_task(task):
    progress = task_progress(task)
    assignees = clean_list(task.get("assignees"))
    tags = clean_list(task.get("tags"))
    risk_text, risk_class = risk_label(task)
    chips = "".join(f'<span class="chip">👤 {html.escape(name)}</span>' for name in assignees)
    tag_chips = "".join(f'<span class="chip">🏷️ {html.escape(tag)}</span>' for tag in tags)
    title = html.escape(str(task.get("title") or "未命名任務"))
    due_text = task_due(task).strftime("%Y-%m-%d")
    task_id = parse_int(task.get("id"), 0)
    checklist = normalize_checklist(task.get("checklist"))
    completed_items = sum(item["completed"] for item in checklist)
    checklist_summary = (
        f'<div class="task-meta">☑️ 子項目 {completed_items}/{len(checklist)}</div>'
        if checklist else ""
    )

    st.markdown(
        f"""
        <div class="task-card">
          <div class="task-title">📌 {title}</div>
          <div>{chips or '<span class="chip">未指派</span>'}</div>
          <div class="task-meta">📅 {due_text}　｜　⏱️ {parse_float(task.get('hours_spent'), 0):.1f} 小時</div>
          <span class="chip {risk_class}">{risk_text}</span>
          <span class="chip">重要：{html.escape(str(task.get('importance', '低')))}</span>
          <span class="chip">緊急：{html.escape(str(task.get('urgency', '低')))}</span>
          <div class="progress-bg"><div class="progress-fg" style="width:{progress}%"></div></div>
          <div class="task-meta">進度 {progress}%</div>
          {checklist_summary}
          <div>{tag_chips}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander(f"☑️ 子項目 Checklist｜{completed_items}/{len(checklist)}", expanded=False):
        if checklist:
            with st.form(f"checklist_update_{task_id}"):
                auth1, auth2 = st.columns(2)
                with auth1:
                    checklist_account = st.text_input("操作人工號", key=f"checklist_account_{task_id}")
                with auth2:
                    checklist_password = st.text_input(
                        "操作人密碼", type="password", key=f"checklist_password_{task_id}"
                    )

                updated_checklist = []
                delete_ids = []
                for item in checklist:
                    item_id = int(item["id"])
                    done_col, title_col, owner_col, due_col, delete_col = st.columns([0.55, 2.5, 1.2, 1.2, 0.65])
                    with done_col:
                        completed = st.checkbox("完成", value=item["completed"], key=f"check_done_{task_id}_{item_id}")
                    with title_col:
                        item_title = st.text_input("子項目", value=item["title"], key=f"check_title_{task_id}_{item_id}")
                    with owner_col:
                        owner_options = [""] + list(dict.fromkeys(partner_names + [item["assignee"]]))
                        assignee = st.selectbox(
                            "負責人", owner_options,
                            index=owner_options.index(item["assignee"]) if item["assignee"] in owner_options else 0,
                            key=f"check_owner_{task_id}_{item_id}",
                        )
                    with due_col:
                        due_value = parse_date(item["due"], task_due(task))
                        item_due = st.date_input("期限", due_value, key=f"check_due_{task_id}_{item_id}")
                    with delete_col:
                        remove = st.checkbox("刪除", key=f"check_delete_{task_id}_{item_id}")
                    if remove:
                        delete_ids.append(item_id)
                    elif item_title.strip():
                        updated_checklist.append({
                            "id": item_id,
                            "title": item_title.strip(),
                            "completed": completed,
                            "assignee": assignee,
                            "due": item_due.strftime("%Y-%m-%d"),
                        })

                save_checklist = st.form_submit_button("儲存子項目", width="stretch")

            if save_checklist:
                try:
                    editor_name = persist_task(
                        task,
                        {"checklist": updated_checklist},
                        checklist_account,
                        checklist_password,
                    )
                    st.success(f"子項目已更新。操作人：{editor_name}")
                    st.rerun()
                except Exception as exc:
                    st.error(f"子項目更新失敗：{exc}")
        else:
            st.caption("目前尚未建立子項目。")

        with st.form(f"checklist_add_{task_id}", clear_on_submit=True):
            st.markdown("##### 新增子項目")
            add_auth1, add_auth2 = st.columns(2)
            with add_auth1:
                add_account = st.text_input("新增人工號", key=f"check_add_account_{task_id}")
            with add_auth2:
                add_password = st.text_input("新增人密碼", type="password", key=f"check_add_password_{task_id}")
            add1, add2, add3 = st.columns([2.4, 1.2, 1.2])
            with add1:
                new_item_title = st.text_input("子項目名稱", key=f"check_add_title_{task_id}")
            with add2:
                new_item_assignee = st.selectbox("負責人", [""] + partner_names, key=f"check_add_owner_{task_id}")
            with add3:
                new_item_due = st.date_input("期限", task_due(task), key=f"check_add_due_{task_id}")
            add_submitted = st.form_submit_button("新增子項目", width="stretch")

        if add_submitted:
            if not new_item_title.strip():
                st.error("請輸入子項目名稱。")
            else:
                try:
                    new_checklist = checklist + [
                        create_checklist_item(checklist, new_item_title, new_item_assignee, new_item_due)
                    ]
                    editor_name = persist_task(
                        task,
                        {"checklist": new_checklist},
                        add_account,
                        add_password,
                    )
                    st.success(f"子項目已新增。操作人：{editor_name}")
                    st.rerun()
                except Exception as exc:
                    st.error(f"子項目新增失敗：{exc}")

    attachments = TaskAttachmentService.load_for_task(task_id)
    with st.expander(f"📎 任務附件｜{len(attachments)}", expanded=False):
        with st.form(f"attachment_upload_{task_id}", clear_on_submit=True):
            attachment_auth1, attachment_auth2 = st.columns(2)
            with attachment_auth1:
                attachment_account = st.text_input("上傳人工號", key=f"attachment_account_{task_id}")
            with attachment_auth2:
                attachment_password = st.text_input(
                    "上傳人密碼", type="password", key=f"attachment_password_{task_id}"
                )
            uploaded_attachment = st.file_uploader(
                "選擇附件（單檔上限 20 MB）",
                type=["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "csv", "txt", "zip", "jpg", "jpeg", "png", "webp", "dwg", "dxf"],
                key=f"task_attachment_file_{task_id}",
            )
            upload_submitted = st.form_submit_button("上傳附件", width="stretch")

        if upload_submitted:
            ok, message, uploader = UserService.authenticate(attachment_account, attachment_password)
            if not ok:
                st.error(message)
            elif uploaded_attachment is None:
                st.error("請先選擇附件。")
            else:
                try:
                    uploader_name = uploader.get("name") or uploader.get("account") or attachment_account
                    TaskAttachmentService.upload(
                        task_id, uploaded_attachment, uploader_name,
                        uploader.get("account", attachment_account),
                    )
                    st.success("附件已上傳。")
                    st.rerun()
                except Exception as exc:
                    st.error(f"附件上傳失敗：{exc}")

        if not attachments:
            st.caption("目前尚無附件。")
        for attachment in attachments:
            attachment_id = parse_int(attachment.get("id"), 0)
            file_name = str(attachment.get("file_name") or "附件")
            meta_col, download_col = st.columns([4, 1])
            with meta_col:
                st.markdown(f"📄 **{html.escape(file_name)}**")
                st.caption(
                    f"{TaskAttachmentService.format_size(attachment.get('size_bytes'))} · "
                    f"{attachment.get('uploaded_by', '')} · {attachment.get('created_at', '')}"
                )
            with download_col:
                download_key = f"attachment_bytes_{task_id}_{attachment_id}"
                if st.button("準備下載", key=f"prepare_attachment_{task_id}_{attachment_id}", width="stretch"):
                    try:
                        st.session_state[download_key] = TaskAttachmentService.download(attachment)
                    except Exception as exc:
                        st.error(f"附件讀取失敗：{exc}")
                if download_key in st.session_state:
                    st.download_button(
                        "下載", data=st.session_state[download_key], file_name=file_name,
                        mime=str(attachment.get("mime_type") or "application/octet-stream"),
                        key=f"download_attachment_{task_id}_{attachment_id}", width="stretch",
                    )

            with st.form(f"attachment_delete_{task_id}_{attachment_id}"):
                delete_attachment1, delete_attachment2, delete_attachment3 = st.columns([1.4, 1.4, 1])
                with delete_attachment1:
                    attachment_deleter_account = st.text_input(
                        "刪除人工號", key=f"attachment_deleter_account_{task_id}_{attachment_id}"
                    )
                with delete_attachment2:
                    attachment_deleter_password = st.text_input(
                        "刪除人密碼", type="password",
                        key=f"attachment_deleter_password_{task_id}_{attachment_id}",
                    )
                with delete_attachment3:
                    delete_attachment_submitted = st.form_submit_button("刪除附件", width="stretch")
            if delete_attachment_submitted:
                ok, message, deleter = UserService.authenticate(
                    attachment_deleter_account, attachment_deleter_password
                )
                if not ok:
                    st.error(message)
                else:
                    try:
                        deleter_name = deleter.get("name") or deleter.get("account") or attachment_deleter_account
                        TaskAttachmentService.delete(
                            attachment_id, task_id, deleter_name,
                            deleter.get("account", attachment_deleter_account),
                        )
                        st.success("附件已刪除並移至垃圾桶。")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"附件刪除失敗：{exc}")
            st.divider()

    with st.expander("✏️ 修改任務／回報進度", expanded=False):
        current_category = str(task.get("category") or "待辦事項")
        category_options = list(dict.fromkeys(STATUS_ORDER + st.session_state.get("categories", [])))
        current_people = list(dict.fromkeys(partner_names + assignees))
        with st.form(f"edit_task_{task_id}"):
            editor1, editor2 = st.columns(2)
            with editor1:
                editor_account = st.text_input("修改人帳號／工號", key=f"editor_account_{task_id}")
            with editor2:
                editor_password = st.text_input("修改人密碼", type="password", key=f"editor_password_{task_id}")

            edit_title = st.text_input("任務名稱", value=str(task.get("title", "")))
            e1, e2 = st.columns(2)
            with e1:
                edit_category = st.selectbox(
                    "任務狀態", category_options,
                    index=category_options.index(current_category) if current_category in category_options else 0,
                )
                edit_due = st.date_input("截止日期", task_due(task))
                edit_progress = st.slider("完成進度", 0, 100, progress, step=5)
            with e2:
                edit_assignees = st.multiselect("指派人員", current_people, default=assignees)
                edit_importance = st.selectbox("重要度", ["高", "低"], index=0 if task.get("importance") == "高" else 1)
                edit_urgency = st.selectbox("緊急度", ["高", "低"], index=0 if task.get("urgency") == "高" else 1)
            edit_tags = st.text_input("標籤", value=",".join(tags))
            edit_notes = st.text_area("備註", value=str(task.get("notes", "")))
            add_hours = st.number_input("本次新增工時", min_value=0.0, step=0.5, value=0.0)
            edit_notify_channels = st.multiselect(
                "儲存後通知管道",
                ["Teams", "Outlook", "LINE"],
                default=["Teams", "Outlook", "LINE"],
                key=f"notify_channels_{task_id}",
            )

            if st.form_submit_button("儲存修改", width="stretch"):
                if not editor_account.strip() or not editor_password:
                    st.error("請輸入修改人的帳號與密碼。")
                elif not edit_title.strip():
                    st.error("任務名稱不可空白。")
                elif not edit_assignees:
                    st.error("請至少保留一位指派人員。")
                else:
                    changes = {
                        "title": edit_title.strip(), "category": edit_category,
                        "due": edit_due, "assignees": edit_assignees,
                        "department": encode_departments(
                            assignee_departments(edit_assignees),
                            fallback=str(task.get("department") or current_department()),
                        ),
                        "progress": edit_progress,
                        "hours_spent": parse_float(task.get("hours_spent"), 0) + add_hours,
                        "importance": edit_importance, "urgency": edit_urgency,
                        "tags": ",".join(clean_list(edit_tags)), "notes": edit_notes.strip(),
                    }
                    try:
                        editor_name = persist_task(task, changes, editor_account, editor_password)
                        event = "completed" if edit_progress >= 100 and progress < 100 else "updated"
                        updated_task = {**task, **changes}
                        if event == "updated" and is_overdue(updated_task):
                            event = "overdue"
                        result = notification_service.send_task_event(
                            event=event,
                            task=updated_task,
                            actor=editor_name,
                            channels=[channel.lower() for channel in edit_notify_channels],
                        )
                        st.session_state["task_notification_result"] = result
                        st.success(f"任務已更新。修改人：{editor_name}")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"任務更新失敗：{exc}")

        st.markdown("##### 🗑️ 刪除任務")
        st.warning("刪除後任務會從看板隱藏，但資料及操作歷程仍保留在 Google Sheet。")
        with st.form(f"delete_task_{task_id}"):
            delete_auth1, delete_auth2 = st.columns(2)
            with delete_auth1:
                deleter_account = st.text_input(
                    "刪除人工號",
                    key=f"task_deleter_account_{task_id}",
                )
            with delete_auth2:
                deleter_password = st.text_input(
                    "刪除人密碼",
                    type="password",
                    key=f"task_deleter_password_{task_id}",
                )
            delete_confirmed = st.checkbox(
                f"我確認要刪除「{task.get('title', '')}」",
                key=f"task_delete_confirmed_{task_id}",
            )
            delete_notify_channels = st.multiselect(
                "刪除後通知管道",
                ["Teams", "Outlook", "LINE"],
                default=["Teams", "Outlook", "LINE"],
                key=f"delete_notify_channels_{task_id}",
            )
            delete_submitted = st.form_submit_button(
                "確認刪除任務",
                type="primary",
                width="stretch",
            )

        if delete_submitted:
            if not deleter_account.strip() or not deleter_password:
                st.error("請輸入刪除人自己的工號與密碼。")
            elif not delete_confirmed:
                st.error("請先勾選刪除確認。")
            else:
                ok, message, deleter = UserService.authenticate(
                    deleter_account,
                    deleter_password,
                )
                if not ok:
                    st.error(message)
                else:
                    deleter_name = (
                        deleter.get("name")
                        or deleter.get("account")
                        or deleter_account
                    )
                    try:
                        deleted_task = TaskService.delete_task(
                            task_id,
                            author=deleter_name,
                            account=deleter.get("account", deleter_account),
                        )
                        result = notification_service.send_task_event(
                            event="deleted",
                            task=deleted_task,
                            actor=deleter_name,
                            channels=[
                                channel.lower()
                                for channel in delete_notify_channels
                            ],
                        )
                        st.session_state["task_notification_result"] = result
                        st.success(f"任務已刪除。操作人：{deleter_name}")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"任務刪除失敗：{exc}")

        with st.expander("💬 留言與操作歷程", expanded=False):
            with st.form(f"task_comment_{task_id}", clear_on_submit=True):
                comment_auth1, comment_auth2 = st.columns(2)
                with comment_auth1:
                    comment_account = st.text_input("留言人工號", key=f"comment_account_{task_id}")
                with comment_auth2:
                    comment_password = st.text_input(
                        "留言人密碼", type="password", key=f"comment_password_{task_id}"
                    )
                comment_text = st.text_area(
                    "留言內容", max_chars=2000, key=f"comment_text_{task_id}",
                    placeholder="輸入進度說明、交辦事項或處理結果……",
                )
                comment_submitted = st.form_submit_button("送出留言", width="stretch")

            if comment_submitted:
                ok, message, commenter = UserService.authenticate(comment_account, comment_password)
                if not ok:
                    st.error(message)
                elif not comment_text.strip():
                    st.error("請輸入留言內容。")
                else:
                    try:
                        commenter_name = commenter.get("name") or commenter.get("account") or comment_account
                        TaskActivityService.add_comment(
                            task_id, commenter_name, commenter.get("account", comment_account), comment_text
                        )
                        st.success("留言已送出。")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"留言失敗：{exc}")

            activities = TaskActivityService.load_for_task(task_id)
            legacy_history = task.get("history") or []
            if not activities and not legacy_history:
                st.caption("目前尚無留言或操作紀錄。")
            for activity in reversed(activities[-50:]):
                event_type = str(activity.get("event_type") or "")
                icon = "💬" if event_type == "commented" else "📜"
                actor = html.escape(str(activity.get("actor") or "系統"))
                created_at = html.escape(str(activity.get("created_at") or ""))
                summary = html.escape(str(activity.get("summary") or ""))
                st.markdown(f"{icon} **{actor}** · {created_at}")
                if activity.get("comment"):
                    st.write(str(activity.get("comment")))
                elif summary:
                    st.caption(summary)
                st.divider()
            if legacy_history:
                st.caption("舊版歷程")
                for item in reversed(legacy_history[-20:]):
                    st.caption(str(item))


st.divider()
# 看板固定為三個等寬欄位；每欄限制高度，超過三張任務卡後在欄內捲動。
# height 720 約可完整呈現三張一般任務卡（含收合狀態的修改區）。
BOARD_HEIGHT = 720
columns = st.columns(3, gap="medium")
for index, category_name in enumerate(STATUS_ORDER):
    category_tasks = [task for task in filtered_tasks if str(task.get("category")) == category_name]
    category_tasks.sort(key=lambda task: (-priority_score(task), task_due(task), parse_int(task.get("id"), 0)))
    with columns[index]:
        st.subheader(f"{category_name}｜{len(category_tasks)}")
        with st.container(height=BOARD_HEIGHT, border=True):
            if not category_tasks:
                st.info("目前沒有任務。")
            for task in category_tasks:
                render_task(task)
