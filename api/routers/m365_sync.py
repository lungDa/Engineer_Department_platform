import hmac
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from config.settings import get_settings
from repositories.user_repository import user_repository
from services.core import UserService, parse_int


router = APIRouter(
    prefix="/api/m365",
    tags=["Microsoft 365 Directory"],
)

M365_SYNC_SOURCE = "m365"
M365_SYNC_SCOPE = "工程一部"

# 原平台人員固定保護範圍
PROTECTED_USER_IDS = set(range(1, 36))

# 2026/07/23 首次錯誤同步產生的資料範圍
CLEANUP_FIRST_ID = 36
CLEANUP_LAST_ID = 235

# 安全鎖：實際停用數必須完全相符
EXPECTED_DISABLE_COUNT = 193


class M365User(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = Field(default="", max_length=200)
    email: str | None = Field(default="", max_length=320)
    upn: str | None = Field(default="", max_length=320)
    department: str | None = Field(default="", max_length=200)
    job_title: str | None = Field(default="", max_length=200)
    mobile: str | None = Field(default="", max_length=100)
    m365_id: str | None = Field(default="", max_length=200)


def _normalized(value: object) -> str:
    """統一比較格式，避免大小寫或空白造成比對失敗。"""
    return str(value or "").strip().casefold()


def _verify_token(
    received_token: str | None,
    authorization: str | None,
) -> None:
    """驗證 GitHub Actions 傳入的同步權杖。"""
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


def _find_existing_index(
    users: list[dict],
    incoming: M365User,
) -> int | None:
    """使用 M365 ID、UPN、Email、帳號及唯一姓名尋找既有人員。"""
    candidates = (
        ("m365_id", incoming.m365_id),
        ("m365_upn", incoming.upn),
        ("email", incoming.email or incoming.upn),
        ("account", incoming.upn or incoming.email),
    )

    for field, value in candidates:
        needle = _normalized(value)

        if not needle:
            continue

        for index, user in enumerate(users):
            if _normalized(user.get(field)) == needle:
                return index

    name = _normalized(incoming.name)

    if not name:
        return None

    matches = [
        index
        for index, user in enumerate(users)
        if _normalized(user.get("name")) == name
    ]

    # 只有同名資料剛好一筆時，才允許用姓名比對。
    return matches[0] if len(matches) == 1 else None


@router.post("/users/sync")
def sync_m365_users(
    payload: list[M365User],
    x_m365_webhook_token: str | None = Header(
        default=None,
        alias="X-M365-Webhook-Token",
    ),
    authorization: str | None = Header(default=None),
):
    """
    同步工程一部成員，並執行一次性安全清理。

    保護：
    - ID 1～35
    - 本次 M365 工程一部有效成員

    清理：
    - 僅限 ID 36～235
    - 僅停用，不刪除
    - 停用數不是193時不寫入
    """
    _verify_token(
        x_m365_webhook_token,
        authorization,
    )

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="人員清單不可為空。",
        )

    if len(payload) > 1000:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="單次最多同步1000位人員。",
        )

    users = user_repository.get_all()

    next_id = (
        max(
            (parse_int(user.get("id"), 0) for user in users),
            default=0,
        )
        + 1
    )

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    created = 0
    updated = 0
    skipped = 0
    marked = 0

    # 記錄本次真正出現在工程一部群組中的平台ID。
    current_scope_user_ids: set[int] = set()

    for incoming in payload:
        email = str(
            incoming.email
            or incoming.upn
            or ""
        ).strip()

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
            "m365_department": str(
                incoming.department or ""
            ).strip(),
            "department": (
                str(incoming.department or "").strip()
                or M365_SYNC_SCOPE
            ),
            "job_title": str(
                incoming.job_title or ""
            ).strip(),
            "mobile": str(
                incoming.mobile or ""
            ).strip(),
            "m365_id": m365_id,
            "sync_source": M365_SYNC_SOURCE,
            "m365_scope": M365_SYNC_SCOPE,
            "updated_at": now,
        }

        if index is not None:
            users[index].update(m365_fields)
            users[index]["active"] = "TRUE"

            existing_id = parse_int(users[index].get("id"), 0)

            if existing_id > 0:
                current_scope_user_ids.add(existing_id)

            updated += 1
            marked += 1
            continue

        new_user_id = next_id

        users.append(
            {
                "id": new_user_id,
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
            }
        )

        current_scope_user_ids.add(new_user_id)
        next_id += 1
        created += 1
        marked += 1

    # 本次應有26位有效工程一部成員。
    if marked != 26:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"安全檢查未通過：本次有效工程一部人數為{marked}，"
                "預期為26。未寫入任何資料，也未停用任何人。"
            ),
        )

    disable_indexes: list[int] = []

    for index, user in enumerate(users):
        user_id = parse_int(user.get("id"), 0)

        # 永久保護原平台 ID 1～35。
        if user_id in PROTECTED_USER_IDS:
            continue

        # 保護本次出現在工程一部群組中的人員。
        if user_id in current_scope_user_ids:
            continue

        # 只處理首次錯誤同步的固定ID範圍。
        if not CLEANUP_FIRST_ID <= user_id <= CLEANUP_LAST_ID:
            continue

        disable_indexes.append(index)

    # 寫入前的最後安全鎖。
    if len(disable_indexes) != EXPECTED_DISABLE_COUNT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"安全檢查未通過：計算停用人數為{len(disable_indexes)}，"
                f"預期為{EXPECTED_DISABLE_COUNT}。"
                "未寫入任何資料，也未停用任何人。"
            ),
        )

    for index in disable_indexes:
        users[index]["active"] = "FALSE"
        users[index]["updated_at"] = now

    if not user_repository.save_all(users):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "M365 人員資料已完成計算，"
                "但寫入 Google Sheet Users 失敗。"
            ),
        )

    return {
        "ok": True,
        "message": "工程一部同步及舊錯誤同步人員停用完成。",
        "phase": "safe_cleanup",
        "scope": M365_SYNC_SCOPE,
        "received": len(payload),
        "created": created,
        "updated": updated,
        "marked": marked,
        "skipped": skipped,
        "protected_original": len(PROTECTED_USER_IDS),
        "disabled": len(disable_indexes),
        "deleted": 0,
        "total_users": len(users),
    }
