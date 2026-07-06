from fastapi import APIRouter, Depends, Query

from api.dependencies.services import get_task_service

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


@router.get("")
def list_tasks(
    status: str | None = Query(default=None, description="Filter by task status, e.g. Active / Completed"),
    assignee: str | None = Query(default=None, description="Filter by assignee name"),
    limit: int = Query(default=50, ge=1, le=500),
    task_service=Depends(get_task_service),
):
    tasks = task_service.load_all()

    if status:
        tasks = [t for t in tasks if str(t.get("status", "")).strip() == status]

    if assignee:
        tasks = [t for t in tasks if assignee in str(t.get("assignee", ""))]

    return {
        "ok": True,
        "count": len(tasks[:limit]),
        "total": len(tasks),
        "data": tasks[:limit],
    }


@router.get("/active")
def active_tasks(limit: int = Query(default=50, ge=1, le=500), task_service=Depends(get_task_service)):
    tasks = task_service.get_active_tasks()
    return {
        "ok": True,
        "count": len(tasks[:limit]),
        "total": len(tasks),
        "data": tasks[:limit],
    }


@router.get("/completed")
def completed_tasks(limit: int = Query(default=50, ge=1, le=500), task_service=Depends(get_task_service)):
    tasks = task_service.get_completed_tasks()
    return {
        "ok": True,
        "count": len(tasks[:limit]),
        "total": len(tasks),
        "data": tasks[:limit],
    }


@router.get("/assignee/{assignee}")
def tasks_by_assignee(
    assignee: str,
    limit: int = Query(default=50, ge=1, le=500),
    task_service=Depends(get_task_service),
):
    tasks = task_service.get_by_assignee(assignee)
    return {
        "ok": True,
        "assignee": assignee,
        "count": len(tasks[:limit]),
        "total": len(tasks),
        "data": tasks[:limit],
    }
