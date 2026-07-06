from services.base_service import BaseService
from services.core import TaskService as LegacyTaskService


class TaskService(BaseService):
    """V5 task service facade.

    It delegates to the existing services.core.TaskService for compatibility.
    New code should import this class instead of importing from services.core directly.
    """

    service_name = "task"

    def default_tasks(self) -> list[dict]:
        return LegacyTaskService.default_tasks()

    def load_all(self) -> list[dict]:
        return LegacyTaskService.load_all()

    def save_all(self, records: list[dict]) -> None:
        return LegacyTaskService.save_all(records)

    def get_active_tasks(self) -> list[dict]:
        return [task for task in self.load_all() if str(task.get("status", "")).strip() == "Active"]

    def get_completed_tasks(self) -> list[dict]:
        return [task for task in self.load_all() if str(task.get("status", "")).strip() == "Completed"]

    def get_by_assignee(self, assignee: str) -> list[dict]:
        name = str(assignee or "").strip()
        if not name:
            return []
        return [task for task in self.load_all() if name in str(task.get("assignee", ""))]


task_service = TaskService()
