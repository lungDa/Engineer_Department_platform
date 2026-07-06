from repositories.user_repository import user_repository
from services.base_service import BaseService


class AuthService(BaseService):
    """Authentication and user facade using UserRepository."""

    service_name = "auth"

    def load_users(self) -> list[dict]:
        return user_repository.get_all()

    def get_active_users(self) -> list[dict]:
        return user_repository.get_active()

    def get_partner_names(self) -> list[str]:
        return user_repository.get_partner_names()

    def get_by_account(self, account: str) -> dict | None:
        return user_repository.get_by_account(account)

    def get_by_name(self, name: str) -> dict | None:
        return user_repository.get_by_name(name)

    def verify_developer_password(self, password: str) -> tuple[bool, str]:
        if not str(password or "").strip():
            return False, "請輸入開發者密碼。"
        developers = [u for u in self.get_active_users() if self.is_developer_user(u)]
        if not developers:
            return False, "Users 工作表尚未建立開發者帳號。請將開發者的 role 設為「開發者」或 role_level 設為 9 以上。"
        for user in developers:
            if str(user.get("password", "")) == str(password):
                return True, "開發者驗證成功。"
        return False, "開發者密碼錯誤。"

    def is_developer_user(self, user: dict | None) -> bool:
        return user_repository.is_developer_user(user)


auth_service = AuthService()
