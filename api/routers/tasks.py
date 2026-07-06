from fastapi import APIRouter, Depends, Query

from api.dependencies.services import get_task_service

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


@router.get("")
def list_tasks(
    status: str | None = Query(default=None, description="Filter by task status, e.g. Active / Completed"),
    assignee: str | None = Query(default=None, description="Filter by assignee name"),
    category: str | None = Query(default=None, description="Filter by category"),
    importance: str | None = Query(default=None, description="Filter by importance"),
    urgency: str | None = Query(default=None, description="Filter by urgency"),
    keyword: str | None = Query(default=None, description="Search title / notes / category / tags"),
    limit: int = Query(default=50, ge=1, le=500),
    task_service=Depends(get_task_service),
):
    tasks = task_service.query(
        status=status,
        assignee=assignee,
        category=category,
        importance=importance,
        urgency=urgency,
        keyword=keyword,
    )

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


@router.get("/{task_id}")
def task_detail(task_id: int, task_service=Depends(get_task_service)):
    task = task_service.get_by_id(task_id)
    if not task:
        return {
            "ok": False,
            "message": "Task not found",
            "data": None,
        }
    return {
        "ok": True,
        "data": task,
    }
