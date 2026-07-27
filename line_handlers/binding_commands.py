from services.core import UserService


def bind_line_account(text: str, user_id: str | None) -> str | None:
    """Handle `綁定 工號 密碼` without echoing credentials."""
    raw = str(text or "").strip()
    parts = raw.split(maxsplit=2)
    if not parts or parts[0].lower() not in {"綁定", "bind"}:
        return None

    if len(parts) != 3:
        return (
            "🔗 LINE 帳號綁定\n\n"
            "請輸入：綁定 工號 密碼\n"
            "例如：綁定 A001 你的密碼\n\n"
            "提醒：請勿把這則訊息轉傳給他人。"
        )

    account, password = parts[1], parts[2]
    ok, message, user = UserService.bind_line_user(
        account=account,
        password=password,
        line_user_id=user_id or "",
    )
    if not ok:
        return f"❌ {message}\n\n請確認後重新輸入，或聯絡平台管理者。"

    name = str((user or {}).get("name", "")).strip()
    return (
        "✅ LINE 帳號綁定成功\n\n"
        f"人員：{name or account}\n"
        f"工號：{account}\n\n"
        "之後平台的個人 LINE 通知會傳送到這個聊天室。"
    )
