from services.base_service import BaseService
from config.settings import get_settings
from shared.response import failed, success


class LineService(BaseService):
    """LINE service boundary for V5.

    V5.0.2 only prepares the service layer.
    Webhook, Reply, Push and Rich Menu will be implemented in V5.1.
    """

    service_name = "line"

    def is_configured(self) -> bool:
        settings = get_settings()
        return bool(settings.line_channel_secret and settings.line_channel_access_token)

    def get_status(self) -> dict:
        return {
            "configured": self.is_configured(),
            "features": {
                "webhook": False,
                "reply": False,
                "push": False,
                "rich_menu": False,
            },
        }

    def push_text(self, user_id: str, text: str) -> dict:
        if not self.is_configured():
            return failed("LINE 尚未設定 Channel Secret / Access Token。")
        if not user_id:
            return failed("缺少 LINE user_id。")
        self.logger.info("LineService.push_text placeholder called: user_id=%s", user_id)
        return success({"user_id": user_id, "text": text, "pushed": False}, "LINE 推播介面已建立，實際推播將於 V5.1 啟用。")


line_service = LineService()
