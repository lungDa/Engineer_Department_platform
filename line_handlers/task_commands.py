from services.task_service import task_service


def my_tasks_text(user_name: str | None = None, limit: int = 10) -> str:
    """Return task summary text for LINE.

    V5.1.0 starts with generic active tasks. LINE_ID to user mapping will be added
    in V5.1.1, then this can filter by bound user.
    """
    tasks = task_service.get_active_tasks()

    if user_name:
        tasks = task_service.get_by_assignee(user_name)

    if not tasks:
        return "✅ 目前沒有查到進行中的任務。"

    lines = ["📋 我的任務 / 進行中任務", ""]

    for index, task in enumerate(tasks[:limit], start=1):
        title = task.get("title", "未命名任務")
        due = task.get("due", "")
        category = task.get("category", "")
        importance = task.get("importance", "")
        urgency = task.get("urgency", "")
        assignees = task.get("assignees", task.get("assignee", ""))

        lines.append(f"{index}. {title}")
        if category:
            lines.append(f"   專案/分類：{category}")
        if due:
            lines.append(f"   截止：{due}")
        if importance or urgency:
            lines.append(f"   重要/緊急：{importance} / {urgency}")
        if assignees:
            lines.append(f"   指派：{assignees}")
        lines.append("")

    if len(tasks) > limit:
        lines.append(f"尚有 {len(tasks) - limit} 件未列出，請到平台查看完整清單。")

    return "\n".join(lines).strip()
