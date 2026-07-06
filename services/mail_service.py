from services.base_service import BaseService
from shared.response import failed, success


class MailService(BaseService):
    """Mail service placeholder.

    V5.0.2 only defines the service boundary.
    Actual Gmail/SMTP sending will be implemented in V5.3 Automation.
    """

    service_name = "mail"

    def send(self, to: str, subject: str, body: str) -> dict:
        if not to:
            return failed("缺少收件者。")
        self.logger.info("MailService.send placeholder called: to=%s subject=%s", to, subject)
        return success(
            {
                "to": to,
                "subject": subject,
                "body_preview": str(body or "")[:80],
                "sent": False,
            },
            "MailService 尚未啟用實際寄信，已完成介面呼叫。",
        )


mail_service = MailService()
