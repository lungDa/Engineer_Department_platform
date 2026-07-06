from line_handlers.command_router import line_command_router
from services.base_service import BaseService


class LineCommandService(BaseService):
    """Application service for LINE text command handling."""

    service_name = "line_command"

    def handle_text(self, text: str, user_id: str | None = None) -> str:
        return line_command_router.route(text=text, user_id=user_id)


line_command_service = LineCommandService()
