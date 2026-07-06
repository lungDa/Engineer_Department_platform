from repositories.announcement_repository import announcement_repository
from services.base_service import BaseService


class AnnouncementService(BaseService):
    """V5 announcement service using AnnouncementRepository."""

    service_name = "announcement"

    def load_all(self) -> list[dict]:
        return announcement_repository.get_all()

    def save_all(self, records: list[dict]) -> bool:
        return announcement_repository.save_all(records)

    def get_active(self) -> list[dict]:
        return announcement_repository.get_active()

    def query(self, active_only: bool = False, keyword: str | None = None, level: str | None = None) -> list[dict]:
        return announcement_repository.query(active_only=active_only, keyword=keyword, level=level)


announcement_service = AnnouncementService()
