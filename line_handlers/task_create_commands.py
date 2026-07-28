from __future__ import annotations

from datetime import date, datetime
import re

from services.core import UserService, record_department
from services.notification_service import notification_service
from services.task_service import task_service


COMMANDS = {"#任務", "＃任務"}
FIELD_ALIASES = {
    "標題": "title",
    "任務": "title",
    "內容": "notes",
    "說明": "notes",
    "備註": "notes",
    "指派": "assignees",
    "指派人": "assignees",
    "截止": "due",
    "截止日": "due",
    "截止日期": "due",
    "部門": "department",
    "重要": "importance",
    "重要度": "importance",
    "緊急": "urgency",
    "緊急度": "urgency",
    "標籤": "tags",
}


def _format_help(error: str | None = None) -> str:
    prefix = f"❌ {error}\n\n" if error else ""
    return (
        f"{prefix}請依下列格式傳送：\n\n"
        "#任務\n"
        "標題：控制盤圖面確認\n"
        "內容：確認廠商最新版本\n"
        "指派：黃威龍\n"
        "截止：2026-07-30\n\n"
        "可選欄位：部門、重要度、緊急度、標籤\n"
        "多人指派請使用「、」或逗號分隔。"
    )


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


def _parse_fields(text: str) -> tuple[dict, str | None]:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if not lines or lines[0] not in COMMANDS:
        return {}, "not_task_command"

    fields: dict[str, str] = {}
    for line in lines[1:]:
        match = re.match(r"^([^:：]+)\s*[:：]\s*(.*)$", line)
        if not match:
            return {}, f"無法辨識「{line}」，每個欄位都要使用冒號。"
        label, value = match.group(1).strip(), match.group(2).strip()
        key = FIELD_ALIASES.get(label)
        if not key:
            return {}, f"不支援欄位「{label}」。"
        if key in fields:
            return {}, f"欄位「{label}」重複出現。"
        fields[key] = value
    return fields, None


def create_task_from_line(text: str, user_id: str | None) -> str | None:
    """Create a platform task from a bound LINE account.

    Returns None when the message is not a #任務 command, otherwise returns the
    text that should be sent back to LINE.
    """
    fields, parse_error = _parse_fields(text)
    if parse_error == "not_task_command":
        return None
    if parse_error:
        return _format_help(parse_error)

    actor = _bound_user(user_id)
    if not actor:
        return (
            "❌ 尚未綁定平台帳號，任務未建立。\n\n"
            "請先輸入：綁定 工號 密碼"
        )

    missing = [
        label
        for key, label in (("title", "標題"), ("assignees", "指派"), ("due", "截止"))
        if not fields.get(key)
    ]
    if missing:
        return _format_help(f"缺少必要欄位：{'、'.join(missing)}。")

    due = _parse_date(fields["due"])
    if not due:
        return _format_help("截止日期格式錯誤，請使用 YYYY-MM-DD。")

    assignees = _split_names(fields["assignees"])
    active_names = {
        str(user.get("name") or "").strip()
        for user in UserService.get_active_users()
        if str(user.get("name") or "").strip()
    }
    unknown = [name for name in assignees if name not in active_names]
    if unknown:
        return f"❌ 找不到啟用中的人員：{'、'.join(unknown)}。\n\n任務未建立，請修正姓名後重送。"

    importance = fields.get("importance", "低")
    urgency = fields.get("urgency", "低")
    if importance not in {"高", "低"}:
        return _format_help("重要度只能填「高」或「低」。")
    if urgency not in {"高", "低"}:
        return _format_help("緊急度只能填「高」或「低」。")

    actor_name = str(actor.get("name") or actor.get("account") or "LINE 使用者").strip()
    department = fields.get("department") or record_department(actor)
    task = {
        "title": fields["title"],
        "category": "待辦事項",
        "due": due,
        "assignees": assignees,
        "status": "Active",
        "progress": 0,
        "hours_spent": 0.0,
        "department": department,
        "importance": importance,
        "urgency": urgency,
        "tags": fields.get("tags", ""),
        "notes": fields.get("notes", ""),
        "depends_on": [],
        "history": [f"[{datetime.now().strftime('%m-%d %H:%M')}] {actor_name} 透過 LINE 建立任務"],
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
        if failed else
        "\n✅ Teams、Outlook、LINE 通知已處理。"
    )

    return (
        "✅ 任務建立成功\n\n"
        f"編號：{created.get('id')}\n"
        f"標題：{created.get('title')}\n"
        f"指派：{'、'.join(assignees)}\n"
        f"截止：{due:%Y-%m-%d}\n"
        f"建立人：{actor_name}"
        f"{notice}"
    )
