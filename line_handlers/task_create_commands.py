from __future__ import annotations

from datetime import date, datetime, timedelta
import re
from threading import Lock

from services.core import UserService, assignee_departments, encode_departments
from services.notification_service import notification_service
from services.task_service import task_service


COMMANDS = {"#任務", "＃任務"}
CANCEL_COMMANDS = {"取消", "取消任務", "#取消", "＃取消"}
SESSION_TIMEOUT = timedelta(minutes=15)
_sessions: dict[str, dict] = {}
_sessions_lock = Lock()


def _split_names(value: str) -> list[str]:
    names = [
        item.strip()
        for item in re.split(r"[,，、;；]", str(value or ""))
        if item.strip()
    ]
    return list(dict.fromkeys(names))


def _parse_date(value: str) -> date | None:
    normalized = str(value or "").strip().replace("/", "-").replace(".", "-")
    try:
        return datetime.strptime(normalized, "%Y-%m-%d").date()
    except ValueError:
        return None


def _bound_user(line_user_id: str | None) -> dict | None:
    target = str(line_user_id or "").strip()
    if not target:
        return None
    return next(
        (
            user
            for user in UserService.get_active_users()
            if str(user.get("line_user_id") or "").strip() == target
        ),
        None,
    )


def _get_session(user_id: str) -> tuple[dict | None, bool]:
    now = datetime.now()
    with _sessions_lock:
        session = _sessions.get(user_id)
        if session and now - session["updated_at"] > SESSION_TIMEOUT:
            _sessions.pop(user_id, None)
            return None, True
        return session, False


def _start_session(user_id: str, actor: dict) -> None:
    with _sessions_lock:
        _sessions[user_id] = {
            "step": "content",
            "actor": actor,
            "data": {},
            "updated_at": datetime.now(),
        }


def _update_session(user_id: str, *, step: str, **data) -> None:
    with _sessions_lock:
        session = _sessions[user_id]
        session["step"] = step
        session["data"].update(data)
        session["updated_at"] = datetime.now()


def _clear_session(user_id: str) -> None:
    with _sessions_lock:
        _sessions.pop(user_id, None)


def _active_names() -> set[str]:
    return {
        str(user.get("name") or "").strip()
        for user in UserService.get_active_users()
        if str(user.get("name") or "").strip()
    }


def _create_task(session: dict, due: date) -> str:
    actor = session["actor"]
    data = session["data"]
    actor_name = str(
        actor.get("name") or actor.get("account") or "LINE 使用者"
    ).strip()
    content = data["content"]
    assignees = data["assignees"]
    # 同一筆任務會顯示在所有被指派者所屬課別。
    task_department = encode_departments(assignee_departments(assignees))
    task = {
        # 平台資料結構仍需要 title，直接以使用者輸入的內容作為任務名稱。
        "title": content,
        "category": "待辦事項",
        "due": due,
        "assignees": assignees,
        "status": "Active",
        "progress": 0,
        "hours_spent": 0.0,
        "department": task_department,
        "importance": "低",
        "urgency": "低",
        "tags": "",
        "notes": "",
        "depends_on": [],
        "history": [
            f"[{datetime.now().strftime('%m-%d %H:%M')}] "
            f"{actor_name} 透過 LINE 建立任務"
        ],
    }

    try:
        created = task_service.create(
            task,
            author=actor_name,
            account=str(actor.get("account") or ""),
        )
    except Exception as exc:
        return f"❌ 任務寫入失敗，未建立資料。\n\n原因：{exc}"

    try:
        notification = notification_service.send_task_event(
            event="created",
            task=created,
            actor=actor_name,
            channels=("teams", "outlook", "line"),
        )
        failed = notification.get("data", {}).get("failed_channels", [])
    except Exception:
        failed = ["Teams", "Outlook", "LINE"]
    notice = (
        f"\n⚠️ 下列通知失敗：{'、'.join(failed)}，任務資料仍已成功保存。"
        if failed
        else "\n✅ Teams、Outlook、LINE 通知已處理。"
    )

    return (
        "✅ 任務建立成功\n\n"
        f"編號：{created.get('id')}\n"
        f"內容：{content}\n"
        f"指派：{'、'.join(assignees)}\n"
        f"截止：{due:%Y-%m-%d}\n"
        f"平台課別：{task_department}\n"
        f"建立人：{actor_name}"
        f"{notice}"
    )


def create_task_from_line(text: str, user_id: str | None) -> str | None:
    """Run the step-by-step LINE task creation conversation."""
    message = str(text or "").strip()
    target = str(user_id or "").strip()
    session, expired = _get_session(target) if target else (None, False)

    if message in COMMANDS:
        actor = _bound_user(target)
        if not actor:
            return (
                "❌ 尚未綁定平台帳號，任務未建立。\n\n"
                "請先輸入：綁定 工號 密碼"
            )
        _start_session(target, actor)
        return (
            "📝 建立任務（第 1/3 步）\n\n"
            "請輸入任務內容：\n"
            "例如：確認廠商最新版本\n\n"
            "輸入「取消」可結束建立。"
        )

    if not session:
        if expired:
            return "⌛ 任務建立已逾時，請重新輸入「#任務」開始。"
        return None

    if message in CANCEL_COMMANDS:
        _clear_session(target)
        return "已取消建立任務。"

    if session["step"] == "content":
        if not message:
            return "❌ 任務內容不能空白，請重新輸入。"
        if len(message) > 200:
            return "❌ 任務內容請控制在 200 字以內，請重新輸入。"
        _update_session(target, step="assignees", content=message)
        return (
            "👤 建立任務（第 2/3 步）\n\n"
            "請輸入指派人員姓名：\n"
            "例如：黃威龍\n\n"
            "多人請用「、」分隔。"
        )

    if session["step"] == "assignees":
        assignees = _split_names(message)
        if not assignees:
            return "❌ 指派人員不能空白，請重新輸入。"
        unknown = [name for name in assignees if name not in _active_names()]
        if unknown:
            return (
                f"❌ 找不到啟用中的人員：{'、'.join(unknown)}。\n\n"
                "請確認姓名後重新輸入，或輸入「取消」。"
            )
        _update_session(target, step="due", assignees=assignees)
        return (
            "📅 建立任務（第 3/3 步）\n\n"
            "請輸入截止日期：\n"
            "例如：2026-07-30"
        )

    due = _parse_date(message)
    if not due:
        return "❌ 日期格式錯誤，請使用 YYYY-MM-DD，例如：2026-07-30。"
    if due < date.today():
        return "❌ 截止日期不能早於今天，請重新輸入。"

    # 建立前先清除對話，避免 LINE 重送相同 webhook 時重複建立。
    _clear_session(target)
    return _create_task(session, due)
