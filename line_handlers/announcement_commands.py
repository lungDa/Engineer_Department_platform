from services.announcement_service import announcement_service


def announcements_text(limit: int = 5) -> str:
    rows = announcement_service.get_active()

    if not rows:
        return "📢 目前沒有有效公告。"

    lines = ["📢 最新公告", ""]

    for index, ann in enumerate(rows[:limit], start=1):
        title = ann.get("title", "未命名公告")
        level = ann.get("level", "")
        content = ann.get("content", "")
        expires_at = ann.get("expires_at", "")
        author = ann.get("author", "")

        lines.append(f"{index}. {title}")
        if level:
            lines.append(f"   類型：{level}")
        if content:
            preview = str(content).strip()
            if len(preview) > 80:
                preview = preview[:80] + "..."
            lines.append(f"   內容：{preview}")
        if expires_at:
            lines.append(f"   到期：{expires_at}")
        if author:
            lines.append(f"   發布：{author}")
        lines.append("")

    if len(rows) > limit:
        lines.append(f"尚有 {len(rows) - limit} 則公告未列出，請到平台查看完整公告。")

    return "\n".join(lines).strip()
