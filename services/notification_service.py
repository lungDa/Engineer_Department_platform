from __future__ import annotations

from typing import Iterable

from config.settings import get_settings
from services.line_service import line_service
from services.mail_service import mail_service
from services.teams_service import teams_service
from shared.response import success


class NotificationService:
    """Route one business event to LINE, Teams and Outlook independently."""

    @staticmethod
    def _contacts(names: Iterable[str]) -> list[dict]:
        # Local import avoids coupling the core data services during startup.
        from services.core import UserService

        wanted = {str(name).strip() for name in names if str(name).strip()}
        return [
            user for user in UserService.get_active_users()
            if str(user.get("name", "")).strip() in wanted
        ]

    @staticmethod
    def _skipped(message: str) -> dict:
        return {"ok": True, "skipped": True, "message": message, "data": None}

    def send_task_event(
        self,
        *,
        event: str,
        task: dict,
        actor: str,
        channels: Iterable[str] = ("teams", "outlook"),
    ) -> dict:
        enabled = {str(channel).strip().lower() for channel in channels}
        assignees = task.get("assignees") or []
        if isinstance(assignees, str):
            assignees = [item.strip() for item in assignees.replace("；", ",").split(",") if item.strip()]
        contacts = self._contacts(assignees)
        due = str(task.get("due") or "-")
        title = str(task.get("title") or "未命名任務")
        department = str(task.get("department") or "-")
        progress = str(task.get("progress", 0))
        names = "、".join(assignees) or "未指派"
        event_titles = {
            "created": "新增任務",
            "updated": "任務更新",
            "completed": "任務完成",
            "overdue": "任務逾期",
            "deleted": "任務刪除",
        }
        event_title = event_titles.get(event, event)
        message = (
            f"事件：{event_title}\n任務：{title}\n部門：{department}\n"
            f"指派：{names}\n截止：{due}\n進度：{progress}%\n操作人：{actor}"
        )
        results: dict[str, dict] = {}

        if "teams" in enabled:
            results["teams"] = teams_service.send(
                title=f"工程部平台｜{event_title}",
                message=f"{title}（{progress}%）",
                level="warning" if event in {"overdue", "deleted"} else "info",
                facts={"部門": department, "指派人員": names, "截止日期": due, "操作人": actor},
                source_url=get_settings().streamlit_base_url,
            )
        else:
            results["teams"] = self._skipped("未選擇 Teams。")

        if "outlook" in enabled:
            emails = [str(user.get("email", "")).strip() for user in contacts if str(user.get("email", "")).strip()]
            results["outlook"] = (
                mail_service.send(emails, f"[工程部平台] {event_title}｜{title}", message)
                if emails else self._skipped("指派人員尚未設定 Email。")
            )
        else:
            results["outlook"] = self._skipped("未選擇 Outlook。")

        if "line" in enabled:
            line_ids = [str(user.get("line_user_id", "")).strip() for user in contacts if str(user.get("line_user_id", "")).strip()]
            if line_ids:
                sends = [line_service.push_text(line_id, message) for line_id in line_ids]
                results["line"] = {
                    "ok": all(item.get("ok") for item in sends),
                    "message": f"LINE 已處理 {len(sends)} 位收件者。",
                    "data": sends,
                }
            else:
                results["line"] = self._skipped("指派人員尚未設定 LINE User ID。")
        else:
            results["line"] = self._skipped("未選擇 LINE。")

        failed_channels = [name for name, result in results.items() if not result.get("ok")]
        return success(
            {"channels": results, "failed_channels": failed_channels},
            "通知已處理。" if not failed_channels else "部分通知發送失敗。",
        )

    def send_meeting_event(
        self,
        *,
        event: str,
        meeting: dict,
        actor: str,
        channels: Iterable[str] = ("teams", "outlook"),
    ) -> dict:
        enabled = {str(channel).strip().lower() for channel in channels}
        attendees = meeting.get("attendees") or []
        if isinstance(attendees, str):
            attendees = [
                item.strip()
                for item in attendees.replace("；", ",").replace("、", ",").split(",")
                if item.strip()
            ]

        contacts = self._contacts(attendees)
        title = str(meeting.get("title") or "未命名會議")
        meeting_date = str(meeting.get("time") or "-")
        department = str(meeting.get("department") or "-")
        link = str(meeting.get("link") or "").strip()
        notes = str(meeting.get("notes") or "").strip()
        names = "、".join(attendees) or "未指定"
        event_titles = {
            "created": "新增會議",
            "updated": "會議變更",
            "cancelled": "會議取消",
            "reminder": "會議提醒",
        }
        event_title = event_titles.get(event, event)

        message_lines = [
            f"事件：{event_title}",
            f"會議：{title}",
            f"部門：{department}",
            f"日期：{meeting_date}",
            f"與會者：{names}",
            f"操作人：{actor}",
        ]
        if link:
            message_lines.append(f"會議連結：{link}")
        if notes:
            message_lines.append(f"備註：{notes}")
        message = "\n".join(message_lines)

        facts = {
            "部門": department,
            "會議日期": meeting_date,
            "與會者": names,
            "操作人": actor,
        }
        if link:
            facts["會議連結"] = link

        results: dict[str, dict] = {}
        if "teams" in enabled:
            results["teams"] = teams_service.send(
                title=f"工程部平台｜{event_title}",
                message=title,
                level="warning" if event == "cancelled" else "info",
                facts=facts,
                source_url=get_settings().streamlit_base_url,
            )
        else:
            results["teams"] = self._skipped("未選擇 Teams。")

        if "outlook" in enabled:
            emails = [
                str(user.get("email", "")).strip()
                for user in contacts
                if str(user.get("email", "")).strip()
            ]
            results["outlook"] = (
                mail_service.send(
                    emails,
                    f"[工程部平台] {event_title}｜{title}",
                    message,
                )
                if emails
                else self._skipped("與會者尚未設定 Email。")
            )
        else:
            results["outlook"] = self._skipped("未選擇 Outlook。")

        failed_channels = [
            name for name, result in results.items() if not result.get("ok")
        ]
        return success(
            {"channels": results, "failed_channels": failed_channels},
            "通知已處理。" if not failed_channels else "部分通知發送失敗。",
        )


notification_service = NotificationService()
