from __future__ import annotations

from datetime import datetime, timedelta
from threading import Lock

from services.core import UserService


COMMANDS = {"修改密碼", "#修改密碼", "＃修改密碼"}
CANCEL_COMMANDS = {"取消", "#取消", "＃取消"}
SESSION_TIMEOUT = timedelta(minutes=10)
_sessions: dict[str, datetime] = {}
_sessions_lock = Lock()


def _bound_user(line_user_id: str | None) -> dict | None:
    target = str(line_user_id or "").strip()
    return next(
        (
            user
            for user in UserService.get_active_users()
            if str(user.get("line_user_id") or "").strip() == target
        ),
        None,
    )


def change_password_from_line(text: str, user_id: str | None) -> str | None:
    """Update the password of the account bound to the current LINE user."""
    message = str(text or "").strip()
    target = str(user_id or "").strip()
    now = datetime.now()
    with _sessions_lock:
        started_at = _sessions.get(target)
        expired = bool(started_at and now - started_at > SESSION_TIMEOUT)
        if expired:
            _sessions.pop(target, None)
            started_at = None

    if message in COMMANDS:
        actor = _bound_user(target)
        if not actor:
            return (
                "❌ 尚未綁定平台帳號，無法修改密碼。\n\n"
                "請先輸入：綁定 工號 密碼"
            )
        with _sessions_lock:
            _sessions[target] = now
        return (
            "🔐 修改密碼\n\n"
            "請直接輸入新密碼（至少 4 碼）。\n"
            "輸入「取消」可結束修改。\n\n"
            "提醒：請勿將密碼轉傳給他人。"
        )

    if not started_at:
        return "⌛ 修改密碼已逾時，請重新輸入「修改密碼」。" if expired else None
    if message in {"#任務", "＃任務", "#請假", "＃請假", "#加班", "＃加班"}:
        with _sessions_lock:
            _sessions.pop(target, None)
        return None
    if message in CANCEL_COMMANDS:
        with _sessions_lock:
            _sessions.pop(target, None)
        return "已取消修改密碼。"
    if len(message) < 4:
        return "❌ 新密碼至少 4 碼，請重新輸入。"
    if len(message) > 64:
        return "❌ 新密碼不可超過 64 碼，請重新輸入。"

    actor = _bound_user(target)
    if not actor:
        with _sessions_lock:
            _sessions.pop(target, None)
        return "❌ LINE 綁定已失效，請重新綁定後再試。"
    ok, result = UserService.change_password(
        account=str(actor.get("account") or ""),
        old_password="",
        new_password=message,
        confirm_password=message,
        require_old=False,
    )
    if not ok:
        return f"❌ {result}"
    with _sessions_lock:
        _sessions.pop(target, None)
    return (
        "✅ 密碼修改完成\n\n"
        f"人員：{actor.get('name') or actor.get('account')}\n"
        "新密碼已立即生效。"
    )
