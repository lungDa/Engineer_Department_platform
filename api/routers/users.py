from fastapi import APIRouter, Depends, Query

from api.dependencies.services import get_auth_service

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("")
def list_users(department: str | None = Query(default=None), auth_service=Depends(get_auth_service)):
    users = auth_service.load_users()
    if department:
        users = [u for u in users if str(u.get("department") or "儀電規劃課") == department]
    safe_users = []
    for user in users:
        safe = dict(user)
        if "password" in safe:
            safe["password"] = "***"
        if "Password" in safe:
            safe["Password"] = "***"
        safe_users.append(safe)

    return {
        "ok": True,
        "count": len(safe_users),
        "data": safe_users,
    }


@router.get("/active")
def active_users(department: str | None = Query(default=None), auth_service=Depends(get_auth_service)):
    users = auth_service.get_active_users()
    if department:
        users = [u for u in users if str(u.get("department") or "儀電規劃課") == department]
    safe_users = []
    for user in users:
        safe = dict(user)
        if "password" in safe:
            safe["password"] = "***"
        if "Password" in safe:
            safe["Password"] = "***"
        safe_users.append(safe)

    return {
        "ok": True,
        "count": len(safe_users),
        "data": safe_users,
    }


@router.get("/names")
def user_names(auth_service=Depends(get_auth_service)):
    names = auth_service.get_partner_names()
    return {
        "ok": True,
        "count": len(names),
        "data": names,
    }
