from services.base_service import BaseService
from services.core import UserService as LegacyUserService


class AuthService(BaseService):
    """Authentication and user facade for V5.

    This keeps compatibility with the current Users worksheet structure.
    """

    service_name = "auth"

    def load_users(self) -> list[dict]:
        return LegacyUserService.load_all()

    def get_active_users(self) -> list[dict]:
        return LegacyUserService.get_active_users()

    def get_partner_names(self) -> list[str]:
        return LegacyUserService.get_partner_names()

    def verify_developer_password(self, password: str) -> tuple[bool, str]:
        return LegacyUserService.verify_developer_password(password)

    def is_developer_user(self, user: dict | None) -> bool:
        return LegacyUserService.is_developer_user(user)


auth_service = AuthService()
