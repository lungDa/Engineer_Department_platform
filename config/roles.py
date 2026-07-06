# V5.0.2 role definitions

ROLE_DEVELOPER = "開發者"
ROLE_ADMIN = "管理員"
ROLE_MANAGER = "主管"
ROLE_ENGINEER = "工程師"
ROLE_STAFF = "一般人員"
ROLE_GUEST = "訪客"

ROLE_LEVELS = {
    ROLE_GUEST: 0,
    ROLE_STAFF: 1,
    ROLE_ENGINEER: 2,
    ROLE_MANAGER: 5,
    ROLE_ADMIN: 8,
    ROLE_DEVELOPER: 9,
}


def get_role_level(role: str, default: int = 0) -> int:
    return ROLE_LEVELS.get(str(role or "").strip(), default)


def is_admin_level(role_level: int) -> bool:
    return int(role_level or 0) >= ROLE_LEVELS[ROLE_ADMIN]


def is_developer_level(role_level: int) -> bool:
    return int(role_level or 0) >= ROLE_LEVELS[ROLE_DEVELOPER]
