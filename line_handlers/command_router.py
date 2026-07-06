from line_handlers.announcement_commands import announcements_text
from line_handlers.system_commands import help_text, status_text
from line_handlers.task_commands import my_tasks_text


class LineCommandRouter:
    """Routes LINE text commands to platform services."""

    def normalize(self, text: str) -> str:
        return str(text or "").strip().lower().replace(" ", "")

    def route(self, text: str, user_id: str | None = None) -> str:
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
            "・公告"
        )


line_command_router = LineCommandRouter()
