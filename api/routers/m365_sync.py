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


class M365User(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # Microsoft 365 未填寫的欄位可能回傳 null。
    name: str | None = Field(default="", max_length=200)
    email: str | None = Field(default="", max_length=320)
    upn: str | None = Field(default="", max_length=320)
    department: str | None = Field(default="", max_length=200)
    job_title: str | None = Field(default="", max_length=200)
    mobile: str | None = Field(default="", max_length=100)
    m365_id: str | None = Field(default="", max_length=200)


def _extract_account(value: object) -> str:
    """從 M365 電子郵件取得平台帳號。"""
    raw_value = str(value or "").strip()

    if not raw_value:
        return ""

    account_prefix = raw_value.split("@", 1)[0]
    return account_prefix.strip().strip('"').strip("'")


def _verify_token(
    received_token: str | None,
    authorization: str | None,
) -> None:
    """驗證同步請求使用的權杖。"""
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
    """
    依穩定識別資料尋找平台既有人員。

    比對順序：
    1. Microsoft 365 ID
    2. Microsoft 365 UPN
    3. Email
    4. 平台帳號
    5. 唯一姓名
    """
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

    # 只有平台內同名人員剛好一筆時，才允許使用姓名比對。
    name = _normalized(incoming.name)

    if not name:
        return None

    matches = [
        index
        for index, user in enumerate(users)
        if _normalized(user.get("name")) == name
    ]

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
    Microsoft 365 工程一部手動安全同步。

    同步內容：
    - 更新 M365 ID、UPN、Email、電話等基本資料
    - 更新 M365 原始部門與原始職稱
    - 新增第一次出現的 M365 成員
    - 新成員的預設平台部門為「待分類」
    - 將本次同步成員維持為啟用

    不會處理：
    - 不覆蓋平台手動設定的部門
    - 不覆蓋平台角色、職務及權限
    - 不覆蓋密碼、兼任資料及 LINE ID
    - 不停用未出現在 M365 群組中的人員
    - 不刪除任何人員
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
            (
                parse_int(user.get("id"), 0)
                for user in users
            ),
            default=0,
        )
        + 1
    )

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    created = 0
    updated = 0
    skipped = 0
    marked = 0

    for incoming in payload:
        email = str(
            incoming.email
            or incoming.upn
            or ""
        ).strip()

        upn = str(incoming.upn or "").strip()
        name = str(incoming.name or "").strip()
        m365_id = str(incoming.m365_id or "").strip()

        # 姓名與任一帳號識別資料不可同時缺少。
        if not name or not (email or upn or m365_id):
            skipped += 1
            continue

        index = _find_existing_index(users, incoming)

        # 這些欄位由 Microsoft 365 管理。
        # 不包含平台 department、role 或 role_level。
        m365_fields = {
            "name": name,
            "email": email,
            "m365_upn": upn,
            "m365_department": str(
                incoming.department or ""
            ).strip(),
            "m365_job_title": str(
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
            # 僅更新 Microsoft 365 管理的欄位。
            # 平台部門、角色、權限及兼任設定都會保留。
            users[index].update(m365_fields)
            users[index]["active"] = "TRUE"

            updated += 1
            marked += 1
            continue

        # 第一次同步的新成員先放入「待分類」。
        users.append(
            {
                "id": next_id,
                "account": upn or email,
                "department": "待分類",
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

        next_id += 1
        created += 1
        marked += 1

    if not user_repository.save_all(users):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "M365 人員已接收，"
                "但寫入 Google Sheet Users 失敗。"
            ),
        )

    return {
        "ok": True,
        "message": "Microsoft 365 工程一部手動安全同步完成。",
        "phase": "manual_safe_sync",
        "scope": M365_SYNC_SCOPE,
        "received": len(payload),
        "created": created,
        "updated": updated,
        "marked": marked,
        "skipped": skipped,
        "disabled": 0,
        "deleted": 0,
        "total_users": len(users),
        "synced_at": now,
    }
