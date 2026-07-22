import hmac
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from config.settings import get_settings
from repositories.user_repository import user_repository
from services.core import UserService, parse_int


router = APIRouter(prefix="/api/m365", tags=["Microsoft 365 Directory"])


class M365User(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # Office 365 Users may return null for fields that administrators did not fill in.
    name: str | None = Field(default="", max_length=200)
    email: str | None = Field(default="", max_length=320)
    upn: str | None = Field(default="", max_length=320)
    department: str | None = Field(default="", max_length=200)
    job_title: str | None = Field(default="", max_length=200)
    mobile: str | None = Field(default="", max_length=100)
    m365_id: str | None = Field(default="", max_length=200)


def _normalized(value: object) -> str:
    return str(value or "").strip().casefold()


def _verify_token(received_token: str | None, authorization: str | None) -> None:
    expected = get_settings().m365_webhook_token.strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Render 尚未設定 M365_WEBHOOK_TOKEN。",
        )

    supplied = str(received_token or "").strip()
    if not supplied and authorization:
        scheme, _, credentials = authorization.partition(" ")
        if scheme.casefold() == "bearer":
            supplied = credentials.strip()

    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="M365 同步 Token 無效。",
        )


def _find_existing_index(users: list[dict], incoming: M365User) -> int | None:
    candidates = (
        ("m365_id", incoming.m365_id),
        ("m365_upn", incoming.upn),
        ("email", incoming.email or incoming.upn),
        ("account", incoming.upn),
    )
    for field, value in candidates:
        needle = _normalized(value)
        if not needle:
            continue
        for index, user in enumerate(users):
            if _normalized(user.get(field)) == needle:
                return index

    # Name matching is only safe when exactly one platform user has that name.
    name = _normalized(incoming.name)
    matches = [index for index, user in enumerate(users) if name and _normalized(user.get("name")) == name]
    return matches[0] if len(matches) == 1 else None


@router.post("/users/sync")
def sync_m365_users(
    payload: list[M365User],
    x_m365_webhook_token: str | None = Header(default=None, alias="X-M365-Webhook-Token"),
    authorization: str | None = Header(default=None),
):
    """Upsert an Office 365 Users directory snapshot into the Users worksheet.

    M365-owned company fields are refreshed, including the platform department.
    Platform passwords, assignments, LINE IDs and permission levels remain untouched.
    """
    _verify_token(x_m365_webhook_token, authorization)
    if not payload:
        raise HTTPException(status_code=400, detail="人員清單不可為空。")
    if len(payload) > 1000:
        raise HTTPException(status_code=413, detail="單次最多同步 1000 位人員。")

    users = user_repository.get_all()
    next_id = max((parse_int(user.get("id"), 0) for user in users), default=0) + 1
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    created = 0
    updated = 0
    skipped = 0

    for incoming in payload:
        email = str(incoming.email or incoming.upn or "").strip()
        upn = str(incoming.upn or "").strip()
        name = str(incoming.name or "").strip()
        m365_id = str(incoming.m365_id or "").strip()
        if not name or not (email or upn or m365_id):
            skipped += 1
            continue

        index = _find_existing_index(users, incoming)
        m365_fields = {
            "name": name,
            "email": email,
            "m365_upn": upn,
            "m365_department": str(incoming.department or "").strip(),
            # Entra ID is the source of truth for the platform department/category.
            "department": str(incoming.department or "").strip(),
            "job_title": str(incoming.job_title or "").strip(),
            "mobile": str(incoming.mobile or "").strip(),
            "m365_id": m365_id,
            "updated_at": now,
        }

        if index is not None:
            users[index].update(m365_fields)
            updated += 1
            continue

        users.append({
            "id": next_id,
            "account": upn or email,
            "password": UserService.DEFAULT_PASSWORD,
            "role": "助理工程師",
            "role_level": 0,
            "active": "TRUE",
            "assignments": "[]",
            "line_user_id": "",
            "must_change_password": "TRUE",
            "created_at": now,
            "last_login_at": "",
            **m365_fields,
        })
        next_id += 1
        created += 1

    if not user_repository.save_all(users):
        raise HTTPException(status_code=502, detail="M365 人員已接收，但寫入 Google Sheet Users 失敗。")

    return {
        "ok": True,
        "message": "M365 人員同步完成。",
        "received": len(payload),
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "total_users": len(users),
    }
