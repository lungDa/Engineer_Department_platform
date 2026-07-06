from services.base_service import BaseService
from config.settings import get_settings
from shared.response import failed, success


class AIService(BaseService):
    """AI service boundary for V5.

    V5.0.2 prepares the interface only.
    OpenAI/Gemini implementation will be added in V5.2.
    """

    service_name = "ai"

    def is_configured(self) -> bool:
        return bool(get_settings().openai_api_key)

    def ask(self, prompt: str, context: dict | None = None) -> dict:
        if not prompt:
            return failed("缺少 AI prompt。")
        self.logger.info("AIService.ask placeholder called.")
        return success(
            {
                "prompt": prompt,
                "context": context or {},
                "answered": False,
            },
            "AIService 介面已建立，實際 AI 回答將於 V5.2 啟用。",
        )


ai_service = AIService()
