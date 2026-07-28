from line_handlers.announcement_commands import announcements_text
from line_handlers.binding_commands import bind_line_account
from line_handlers.leave_create_commands import create_leave_from_line
from line_handlers.password_commands import change_password_from_line
from line_handlers.system_commands import help_text, status_text
from line_handlers.task_create_commands import create_task_from_line
from line_handlers.task_commands import my_tasks_text


class LineCommandRouter:
    """Routes LINE text commands to platform services."""

    def normalize(self, text: str) -> str:
        return str(text or "").strip().lower().replace(" ", "")

    def route(self, text: str, user_id: str | None = None) -> str:
        binding_reply = bind_line_account(text=text, user_id=user_id)
        if binding_reply is not None:
            return binding_reply

        # 新流程指令優先於既有問答狀態，避免「#請假」被當成密碼或任務內容。
        raw = str(text or "").strip()
        if raw in {"#請假", "＃請假"}:
            return create_leave_from_line(text=text, user_id=user_id)
        if raw in {"#任務", "＃任務"}:
            return create_task_from_line(text=text, user_id=user_id)

        password_reply = change_password_from_line(text=text, user_id=user_id)
        if password_reply is not None:
            return password_reply

        leave_reply = create_leave_from_line(text=text, user_id=user_id)
        if leave_reply is not None:
            return leave_reply

        task_create_reply = create_task_from_line(text=text, user_id=user_id)
        if task_create_reply is not None:
            return task_create_reply

        command = self.normalize(text)

        if command in {"", "help", "說明", "幫助", "指令"}:
            return help_text()

        if command in {"狀態", "status", "系統狀態"}:
            return status_text()

        if command in {"我的任務", "任務", "工作", "待辦", "todo", "tasks"}:
            return my_tasks_text()

        if command in {"公告", "布告欄", "announcement", "announcements", "news"}:
            return announcements_text()

        return (
            "我目前還不認得這個指令。\n\n"
            "你可以輸入：\n"
            "・說明\n"
            "・狀態\n"
            "・我的任務\n"
            "・公告\n"
            "・修改密碼\n"
            "・#任務（建立任務）\n"
            "・#請假（建立請假申請）"
        )


line_command_router = LineCommandRouter()
