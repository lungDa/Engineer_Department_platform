from services.config_service import config_service
from services.line_service import line_service


def help_text() -> str:
    return (
        "🤖 開發工程部 LINE 智慧助理\n\n"
        "可用指令：\n"
        "1. 狀態\n"
        "2. 說明\n"
        "3. 我的任務\n"
        "4. 公告\n"
        "5. 綁定 工號 密碼\n"
        "6. #任務（問答式建立任務）\n\n"
        "範例：\n"
        "輸入「我的任務」查詢目前任務。\n"
        "輸入「公告」查詢目前有效公告。\n"
        "輸入「綁定 A001 你的密碼」啟用個人通知。\n\n"
        "建立任務：\n"
        "輸入「#任務」後，系統會依序詢問：\n"
        "1. 任務內容\n"
        "2. 指派人員\n"
        "3. 截止日期\n\n"
        "過程中可輸入「取消」結束建立。"
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
