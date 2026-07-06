from fastapi import APIRouter, Depends, Query

from api.dependencies.services import get_announcement_service

router = APIRouter(prefix="/api/announcements", tags=["Announcements"])


@router.get("")
def list_announcements(
    active_only: bool = Query(default=False),
    keyword: str | None = Query(default=None),
    level: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    announcement_service=Depends(get_announcement_service),
):
    rows = announcement_service.query(active_only=active_only, keyword=keyword, level=level)
    return {
        "ok": True,
        "count": len(rows[:limit]),
        "total": len(rows),
        "data": rows[:limit],
    }


@router.get("/active")
def active_announcements(
    limit: int = Query(default=50, ge=1, le=500),
    announcement_service=Depends(get_announcement_service),
):
    rows = announcement_service.get_active()
    return {
        "ok": True,
        "count": len(rows[:limit]),
        "total": len(rows),
        "data": rows[:limit],
    }
