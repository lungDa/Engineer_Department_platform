from __future__ import annotations

from datetime import date, datetime, timedelta
import re
from threading import Lock

from services.core import ApprovalService, UserService, record_department
from services.notification_service import notification_service


COMMANDS = {"#請假", "＃請假"}
CANCEL_COMMANDS = {"取消", "取消請假", "#取消", "＃取消"}
LEAVE_TYPES = {"特休", "事假", "病假", "公假", "婚假", "喪假", "其他"}
TIME_OPTIONS = {
    f"{hour:02d}:{minute:02d}"
    for hour in range(8, 18)
    for minute in (0, 30)
    if (hour, minute) >= (8, 30) and (hour, minute) <= (17, 30)
}
SESSION_TIMEOUT = timedelta(minutes=20)
_sessions: dict[str, dict] = {}
_sessions_lock = Lock()


def _bound_user(line_user_id: str | None) -> dict | None:
    target = str(line_user_id or "").strip()
    return next(
        (u for u in UserService.get_active_users()
         if str(u.get("line_user_id") or "").strip() == target),
        None,
    )


def _split_names(value: str) -> list[str]:
    values = [x.strip() for x in re.split(r"[,，、;；]", str(value or "")) if x.strip()]
    return list(dict.fromkeys(values))


def _parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(
            str(value or "").strip().replace("/", "-").replace(".", "-"),
            "%Y-%m-%d",
        ).date()
    except ValueError:
        return None


def _get_session(user_id: str) -> tuple[dict | None, bool]:
    now = datetime.now()
    with _sessions_lock:
        session = _sessions.get(user_id)
        if session and now - session["updated_at"] > SESSION_TIMEOUT:
            _sessions.pop(user_id, None)
            return None, True
        return session, False


def _update(user_id: str, step: str, **data) -> None:
    with _sessions_lock:
        _sessions[user_id]["step"] = step
        _sessions[user_id]["data"].update(data)
        _sessions[user_id]["updated_at"] = datetime.now()


def _clear(user_id: str) -> None:
    with _sessions_lock:
        _sessions.pop(user_id, None)


def _save(session: dict) -> str:
    actor, data = session["actor"], session["data"]
    actor_name = str(actor.get("name") or actor.get("account") or "LINE 使用者")
    approval = {
        "type": "請假單",
        "leave_type": data["leave_type"],
        "start_date": data["start_date"],
        "end_date": data["end_date"],
        "start_time": data["start_time"],
        "end_time": data["end_time"],
        "leave_hours": data["leave_hours"],
        "content": data["content"],
        "sender": actor_name,
        "sender_account": str(actor.get("account") or ""),
        "notified_users": data["notified_users"],
        "current_signer": "",
        "status": "已送出",
        "department": record_department(actor),
        "history": [
            f"[{datetime.now():%m-%d %H:%M}] {actor_name} 透過 LINE 送出請假申請"
        ],
    }
    try:
        ApprovalService.add_approval(
            approval, author=actor_name, account=str(actor.get("account") or "")
        )
    except Exception as exc:
        return f"❌ 請假資料寫入失敗，未建立資料。\n\n原因：{exc}"
    try:
        result = notification_service.send_leave_event(
            event="created", approval=approval, actor=actor_name,
            channels=("teams", "outlook", "line"),
        )
        failed = (result.get("data") or {}).get("failed_channels", [])
    except Exception:
        failed = ["Teams", "Outlook", "LINE"]
    notice = (
        f"\n⚠️ 下列通知失敗：{'、'.join(failed)}，請假資料仍已保存。"
        if failed else "\n✅ Teams、Outlook、LINE 通知已處理。"
    )
    return (
        "✅ 請假申請已送出\n\n"
        f"編號：{approval.get('id')}\n申請人：{actor_name}\n"
        f"假別：{data['leave_type']}\n"
        f"日期：{data['start_date']:%Y-%m-%d} ～ {data['end_date']:%Y-%m-%d}\n"
        f"時段：{data['start_time']} ～ {data['end_time']}（{data['leave_hours']:g} 小時）\n"
        f"被通知者：{'、'.join(data['notified_users'])}\n"
        f"已寫入簽核中心及專案行事曆。{notice}"
    )


def create_leave_from_line(text: str, user_id: str | None) -> str | None:
    """Run the step-by-step LINE leave application conversation."""
    message, target = str(text or "").strip(), str(user_id or "").strip()
    session, expired = _get_session(target) if target else (None, False)
    if message in COMMANDS:
        actor = _bound_user(target)
        if not actor:
            return "❌ 尚未綁定平台帳號，請假未建立。\n\n請先輸入：綁定 工號 密碼"
        with _sessions_lock:
            _sessions[target] = {
                "step": "leave_type", "actor": actor, "data": {},
                "updated_at": datetime.now(),
            }
        return (
            "🏖️ 請假申請（第 1/8 步）\n\n"
            "請輸入假別：\n特休、事假、病假、公假、婚假、喪假、其他\n\n"
            "輸入「取消」可結束申請。"
        )
    if not session:
        return "⌛ 請假申請已逾時，請重新輸入「#請假」。" if expired else None
    if message in CANCEL_COMMANDS:
        _clear(target)
        return "已取消請假申請。"

    step, data = session["step"], session["data"]
    if step == "leave_type":
        if message not in LEAVE_TYPES:
            return "❌ 假別不正確，請輸入：特休、事假、病假、公假、婚假、喪假或其他。"
        _update(target, "start_date", leave_type=message)
        return "📅 請假申請（第 2/8 步）\n\n請輸入開始日期，例如：2026-07-30"
    if step == "start_date":
        value = _parse_date(message)
        if not value or value < date.today():
            return "❌ 開始日期格式錯誤或早於今天，請使用 YYYY-MM-DD。"
        _update(target, "end_date", start_date=value)
        return "📅 請假申請（第 3/8 步）\n\n請輸入結束日期，例如：2026-07-30"
    if step == "end_date":
        value = _parse_date(message)
        if not value or value < data["start_date"]:
            return "❌ 結束日期格式錯誤或早於開始日期，請使用 YYYY-MM-DD。"
        _update(target, "start_time", end_date=value)
        return "🕣 請假申請（第 4/8 步）\n\n請輸入開始時間（08:30～17:30，每 30 分鐘），例如：08:30"
    if step == "start_time":
        if message not in TIME_OPTIONS:
            return "❌ 時間格式錯誤，請輸入 08:30～17:30 間的半小時時段。"
        _update(target, "end_time", start_time=message)
        return "🕠 請假申請（第 5/8 步）\n\n請輸入結束時間，例如：17:30"
    if step == "end_time":
        if message not in TIME_OPTIONS:
            return "❌ 時間格式錯誤，請輸入 08:30～17:30 間的半小時時段。"
        if data["start_date"] == data["end_date"] and message <= data["start_time"]:
            return "❌ 同一天請假時，結束時間必須晚於開始時間。"
        _update(target, "leave_hours", end_time=message)
        return "⏱️ 請假申請（第 6/8 步）\n\n請輸入請假時數（最少 0.5 小時），例如：8"
    if step == "leave_hours":
        try:
            value = float(message)
        except ValueError:
            value = 0
        if value < 0.5 or not (value * 2).is_integer():
            return "❌ 請假時數最少為 0.5 小時，且只能以 0.5 小時為單位。"
        if data["start_date"] == data["end_date"]:
            start = int(data["start_time"][:2]) * 60 + int(data["start_time"][3:])
            end = int(data["end_time"][:2]) * 60 + int(data["end_time"][3:])
            if value > (end - start) / 60:
                return "❌ 請假時數不可超過所選開始與結束時間。"
        _update(target, "content", leave_hours=value)
        return "📝 請假申請（第 7/8 步）\n\n請輸入請假說明；若無說明請輸入「無」。"
    if step == "content":
        if not message:
            return "❌ 請假說明不能空白；若無說明請輸入「無」。"
        _update(target, "notified_users", content="" if message == "無" else message[:500])
        return (
            "🔔 請假申請（第 8/8 步）\n\n請輸入被通知者姓名：\n"
            "例如：黃威龍\n\n多人請用「、」分隔。"
        )

    names = _split_names(message)
    active_names = {
        str(u.get("name") or "").strip() for u in UserService.get_active_users()
        if str(u.get("name") or "").strip()
    }
    unknown = [name for name in names if name not in active_names]
    if not names:
        return "❌ 請至少輸入一位被通知者。"
    if unknown:
        return f"❌ 找不到啟用中的人員：{'、'.join(unknown)}。請重新輸入。"
    _update(target, "complete", notified_users=names)
    completed, _ = _get_session(target)
    _clear(target)
    return _save(completed)
