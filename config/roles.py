"""平台角色與權限等級：9 最高，0 最低。"""

ROLE_DEVELOPER = "開發者"
ROLE_VICE_GENERAL_MANAGER = "副總經理"
ROLE_MANAGER = "經理"
ROLE_DEPUTY_MANAGER = "副理"
ROLE_ADMINISTRATOR = "管理師"
ROLE_PROJECT_MANAGER = "專案經理"
ROLE_SECTION_CHIEF = "課長"
ROLE_TEAM_LEADER = "組長"
ROLE_SENIOR_ENGINEER = "資深工程師"
ROLE_ENGINEER = "工程師"
ROLE_ASSISTANT_ENGINEER = "助理工程師"

ROLE_LEVELS = {
    ROLE_DEVELOPER: 9,
    ROLE_VICE_GENERAL_MANAGER: 8,
    ROLE_MANAGER: 8,
    ROLE_DEPUTY_MANAGER: 7,
    ROLE_ADMINISTRATOR: 6,
    ROLE_PROJECT_MANAGER: 5,
    ROLE_SECTION_CHIEF: 4,
    ROLE_TEAM_LEADER: 3,
    ROLE_SENIOR_ENGINEER: 2,
    ROLE_ENGINEER: 1,
    ROLE_ASSISTANT_ENGINEER: 0,
}

PERSONNEL_MANAGEMENT_MIN_LEVEL = 6
DEVELOPER_LEVEL = 9


def get_role_level(role: str, default: int = 0) -> int:
    return ROLE_LEVELS.get(str(role or "").strip(), default)


def can_manage_personnel(role_level: int) -> bool:
    return int(role_level or 0) >= PERSONNEL_MANAGEMENT_MIN_LEVEL


def is_admin_level(role_level: int) -> bool:
    """舊名稱相容：管理人員名單需 6 以上。"""
    return can_manage_personnel(role_level)


def is_developer_level(role_level: int) -> bool:
    return int(role_level or 0) >= DEVELOPER_LEVEL
