from services.config_service import config_service
from services.line_service import line_service


def help_text() -> str:
    return (
        "🤖 開發工程部 LINE 智慧助理\n\n"
        "可用指令：\n"
        "1. 狀態\n"
        "2. 說明\n"
        "3. 我的任務\n"
        "4. 公告\n\n"
        "範例：\n"
        "輸入「我的任務」查詢目前任務。\n"
        "輸入「公告」查詢目前有效公告。"
    )


def status_text() -> str:
    info = config_service.get_public_info()
    line_status = line_service.get_status()

    return (
        "✅ 系統狀態\n\n"
        f"平台：{info.get('app_name')}\n"
        f"版本：{info.get('app_version')}\n"
        f"環境：{info.get('environment')}\n"
        f"LINE 設定：{'已設定' if line_status.get('configured') else '尚未設定'}"
    )
