from repositories.task_repository import task_repository
from services.base_service import BaseService


class TaskService(BaseService):
    """V5 task service using TaskRepository.

    Existing pages can keep using services.core.TaskService.
    New API / LINE / AI features should use this V5 service.
    """

    service_name = "task"

    def default_tasks(self) -> list[dict]:
        return task_repository.default_rows()

    def load_all(self) -> list[dict]:
        return task_repository.get_all()

    def save_all(self, records: list[dict]) -> None:
        return task_repository.save_all(records)

    def query(
        self,
        status: str | None = None,
        assignee: str | None = None,
        category: str | None = None,
        importance: str | None = None,
        urgency: str | None = None,
        due_before=None,
        due_after=None,
        keyword: str | None = None,
    ) -> list[dict]:
        return task_repository.query(
            status=status,
            assignee=assignee,
            category=category,
            importance=importance,
            urgency=urgency,
            due_before=due_before,
            due_after=due_after,
            keyword=keyword,
        )

    def get_by_id(self, task_id: int | str) -> dict | None:
        return task_repository.get_by_id(task_id)

    def get_active_tasks(self) -> list[dict]:
        return task_repository.get_active()

    def get_completed_tasks(self) -> list[dict]:
        return task_repository.get_completed()

    def get_by_assignee(self, assignee: str) -> list[dict]:
        return task_repository.get_by_assignee(assignee)


task_service = TaskService()
