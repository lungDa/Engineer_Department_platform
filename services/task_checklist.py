from __future__ import annotations

from datetime import date
from typing import Any


def normalize_checklist(value: Any) -> list[dict[str, Any]]:
    """Return a stable, JSON-serializable checklist structure."""
    if not isinstance(value, list):
        return []

    result: list[dict[str, Any]] = []
    used_ids: set[int] = set()
    next_id = 1

    for raw in value:
        if isinstance(raw, str):
            item = {"title": raw}
        elif isinstance(raw, dict):
            item = raw
        else:
            continue

        title = str(item.get("title") or item.get("name") or "").strip()
        if not title:
            continue

        try:
            item_id = int(item.get("id") or 0)
        except (TypeError, ValueError):
            item_id = 0
        if item_id <= 0 or item_id in used_ids:
            while next_id in used_ids:
                next_id += 1
            item_id = next_id

        used_ids.add(item_id)
        next_id = max(next_id, item_id + 1)
        result.append(
            {
                "id": item_id,
                "title": title,
                "completed": bool(item.get("completed", False)),
                "assignee": str(item.get("assignee") or "").strip(),
                "due": str(item.get("due") or "").strip(),
            }
        )

    return result


def checklist_progress(checklist: Any, fallback: int = 0) -> int:
    items = normalize_checklist(checklist)
    if not items:
        return max(0, min(100, int(fallback or 0)))
    completed = sum(bool(item["completed"]) for item in items)
    return round(completed * 100 / len(items))


def next_checklist_id(checklist: Any) -> int:
    items = normalize_checklist(checklist)
    return max((int(item["id"]) for item in items), default=0) + 1


def create_checklist_item(
    checklist: Any,
    title: str,
    assignee: str = "",
    due: date | str | None = None,
) -> dict[str, Any]:
    due_text = due.strftime("%Y-%m-%d") if isinstance(due, date) else str(due or "").strip()
    return {
        "id": next_checklist_id(checklist),
        "title": str(title).strip(),
        "completed": False,
        "assignee": str(assignee or "").strip(),
        "due": due_text,
    }
