from __future__ import annotations

from typing import Iterable

from config.settings import get_settings
from services.line_service import line_service
from services.mail_service import mail_service
from services.teams_service import teams_service
from shared.response import success
from config.功能開關 import 功能已開啟


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

    @staticmethod
    def _enabled_channels(channels: Iterable[str]) -> set[str]:
        requested = {str(channel).strip().lower() for channel in channels}
        switches = {
            "teams": "Teams通知",
            "outlook": "Outlook通知",
            "line": "LINE通知",
        }
        return {
            channel for channel in requested
            if channel not in switches or 功能已開啟(switches[channel])
        }

    @staticmethod
    def _m365_emails(contacts: Iterable[dict]) -> list[str]:
        return list(dict.fromkeys(
            str(user.get("m365_upn") or user.get("email") or "").strip()
            for user in contacts
            if str(user.get("m365_upn") or user.get("email") or "").strip()
        ))

    def send_task_event(
        self,
        *,
        event: str,
        task: dict,
        actor: str,
        channels: Iterable[str] = ("teams", "outlook", "line"),
    ) -> dict:
        enabled = self._enabled_channels(channels)
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
            teams_recipients = self._m365_emails(contacts)
            results["teams"] = (
                teams_service.send(
                    title=f"工程部平台｜{event_title}",
                    message=f"{title}（{progress}%）",
                    recipients=teams_recipients,
                    level="warning" if event in {"overdue", "deleted"} else "info",
                    facts={"部門": department, "指派人員": names, "截止日期": due, "操作人": actor},
                    source_url=get_settings().streamlit_base_url,
                )
                if teams_recipients
                else self._skipped("指派人員尚未設定 M365 Email。")
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
            line_targets = [
                (
                    str(user.get("name") or "").strip(),
                    str(user.get("line_user_id") or "").strip(),
                )
                for user in contacts
                if str(user.get("line_user_id") or "").strip()
            ]
            if not line_targets:
                results["line"] = self._skipped("指派人員尚未設定 LINE User ID。")
            else:
                line_results = [
                    (name, line_service.push_text(line_user_id, message))
                    for name, line_user_id in line_targets
                ]
                failed_names = [
                    name for name, result in line_results if not result.get("ok")
                ]
                results["line"] = {
                    "ok": not failed_names,
                    "message": (
                        f"LINE 已個別通知：{'、'.join(name for name, _ in line_targets)}"
                        if not failed_names
                        else f"LINE 個人通知失敗：{'、'.join(failed_names)}"
                    ),
                    "data": {
                        "recipient_count": len(line_targets),
                        "failed_names": failed_names,
                    },
                }
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
        channels: Iterable[str] = ("teams", "outlook", "line"),
    ) -> dict:
        enabled = self._enabled_channels(channels)
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
            teams_recipients = self._m365_emails(contacts)
            results["teams"] = (
                teams_service.send(
                    title=f"工程部平台｜{event_title}",
                    message=title,
                    recipients=teams_recipients,
                    level="warning" if event == "cancelled" else "info",
                    facts=facts,
                    source_url=get_settings().streamlit_base_url,
                )
                if teams_recipients
                else self._skipped("與會者尚未設定 M365 Email。")
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

        if "line" in enabled:
            results["line"] = line_service.broadcast_text(message)
        else:
            results["line"] = self._skipped("未選擇 LINE。")

        failed_channels = [
            name for name, result in results.items() if not result.get("ok")
        ]
        return success(
            {"channels": results, "failed_channels": failed_channels},
            "通知已處理。" if not failed_channels else "部分通知發送失敗。",
        )

    def send_leave_event(
        self,
        *,
        event: str,
        approval: dict,
        actor: str,
        channels: Iterable[str] = ("teams", "outlook", "line"),
    ) -> dict:
        """Notify the selected people after a leave or overtime request is saved."""
        enabled = self._enabled_channels(channels)
        notified_users = approval.get("notified_users") or []
        if isinstance(notified_users, str):
            notified_users = [
                item.strip()
                for item in notified_users.replace("；", ",").replace("、", ",").split(",")
                if item.strip()
            ]

        contacts = self._contacts(notified_users)
        names = "、".join(notified_users) or "未指定"
        is_overtime = str(approval.get("type") or "").strip() == "加班單"
        request_name = "加班" if is_overtime else "請假"
        leave_type = str(approval.get("leave_type") or request_name)
        start_date = str(approval.get("start_date") or "-")
        end_date = str(approval.get("end_date") or start_date)
        start_time = str(approval.get("start_time") or "08:30")
        end_time = str(approval.get("end_time") or "17:30")
        leave_hours = str(approval.get("leave_hours") or "0")
        content = str(approval.get("content") or "").strip() or "無"
        event_titles = {
            "created": f"新增{request_name}申請",
            "updated": f"{request_name}申請變更",
            "deleted": f"{request_name}申請刪除",
        }
        event_title = event_titles.get(event, event)
        message = (
            f"事件：{event_title}\n申請人：{actor}\n假別：{leave_type}\n"
            f"日期：{start_date} ～ {end_date}\n"
            f"時段：{start_time} ～ {end_time}（{leave_hours} 小時）\n"
            f"被通知者：{names}\n{'加班事由' if is_overtime else '請假說明'}：{content}"
        )
        results: dict[str, dict] = {}

        if "teams" in enabled:
            teams_recipients = self._m365_emails(contacts)
            results["teams"] = (
                teams_service.send(
                    title=f"工程部平台｜{event_title}",
                    message=f"{actor}｜{leave_type}",
                    recipients=teams_recipients,
                    level="warning" if event == "deleted" else "info",
                    facts={
                        "申請人": actor,
                        "假別": leave_type,
                        "日期": f"{start_date} ～ {end_date}",
                        "時段": f"{start_time} ～ {end_time}（{leave_hours} 小時）",
                        "被通知者": names,
                        ("加班事由" if is_overtime else "請假說明"): content,
                    },
                    source_url=get_settings().streamlit_base_url,
                )
                if teams_recipients
                else self._skipped(
                    f"被通知者尚未設定 M365 Email：{names}"
                )
            )
        else:
            results["teams"] = self._skipped("未選擇 Teams。")

        if "outlook" in enabled:
            emails = [
                str(user.get("email") or user.get("m365_upn") or "").strip()
                for user in contacts
                if str(user.get("email") or user.get("m365_upn") or "").strip()
            ]
            missing_names = [
                name for name in notified_users
                if not any(
                    str(user.get("name", "")).strip() == name
                    and str(user.get("email") or user.get("m365_upn") or "").strip()
                    for user in contacts
                )
            ]
            if emails:
                results["outlook"] = mail_service.send(
                    emails,
                    f"[工程部平台] {event_title}｜{actor}｜{leave_type}",
                    message,
                )
                if missing_names:
                    results["outlook"]["message"] = (
                        f"{results['outlook'].get('message', '')}"
                        f" 未寄送：{'、'.join(missing_names)}（人員名單未設定 Email）。"
                    ).strip()
                    results["outlook"]["missing_recipients"] = missing_names
            else:
                results["outlook"] = self._skipped(
                    f"被通知者尚未設定 Email：{names}"
                )
        else:
            results["outlook"] = self._skipped("未選擇 Outlook。")

        if "line" in enabled:
            line_targets = [
                (
                    str(user.get("name", "")).strip(),
                    str(user.get("line_user_id", "")).strip(),
                )
                for user in contacts
                if str(user.get("line_user_id", "")).strip()
            ]
            missing_line_names = [
                name for name in notified_users
                if not any(
                    str(user.get("name", "")).strip() == name
                    and str(user.get("line_user_id", "")).strip()
                    for user in contacts
                )
            ]
            if line_targets:
                deliveries = [
                    {
                        "name": name,
                        "result": line_service.push_text(line_user_id, message),
                    }
                    for name, line_user_id in line_targets
                ]
                failed_names = [
                    item["name"] for item in deliveries
                    if not item["result"].get("ok")
                ]
                if failed_names:
                    failure_details = [
                        f"{item['name']}：{item['result'].get('message') or '未知錯誤'}"
                        for item in deliveries
                        if not item["result"].get("ok")
                    ]
                    results["line"] = {
                        "ok": False,
                        "message": "LINE 個人推播失敗｜" + "；".join(failure_details),
                        "data": {"deliveries": deliveries},
                    }
                else:
                    notice = f"LINE 已個別通知：{'、'.join(name for name, _ in line_targets)}"
                    if missing_line_names:
                        notice += (
                            f"；未通知：{'、'.join(missing_line_names)}"
                            "（人員名單未設定 LINE User ID）"
                        )
                    results["line"] = {
                        "ok": True,
                        "message": notice,
                        "data": {
                            "deliveries": deliveries,
                            "missing_recipients": missing_line_names,
                        },
                    }
            else:
                results["line"] = self._skipped(
                    f"被通知者尚未設定 LINE User ID：{names}"
                )
        else:
            results["line"] = self._skipped("未選擇 LINE。")

        failed_channels = [
            name for name, result in results.items() if not result.get("ok")
        ]
        return success(
            {"channels": results, "failed_channels": failed_channels},
            "通知已處理。" if not failed_channels else "部分通知發送失敗。",
        )


notification_service = NotificationService()
