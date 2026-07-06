from datetime import date
from typing import Any

import streamlit as st

from repositories.base_repository import BaseRepository
from repositories.sheet_repository import sheet_repository
from services.core import TaskService as LegacyTaskService, parse_date, parse_int


class TaskRepository(BaseRepository):
    """Repository for Tasks worksheet."""

    repository_name = "task"

    worksheet_name = LegacyTaskService.WORKSHEET_NAME
    columns = LegacyTaskService.COLUMNS

    def default_rows(self) -> list[dict]:
        return LegacyTaskService.default_tasks()

    def get_all(self) -> list[dict]:
        records = sheet_repository.load_records(
            self.worksheet_name,
            self.columns,
            self.default_rows(),
        )
        rows = records if records is not None else st.session_state.get("tasks_fallback", self.default_rows())
        return [LegacyTaskService._from_sheet(row) for row in rows if row.get("title")]

    def save_all(self, records: list[dict]) -> None:
        rows = [LegacyTaskService._to_sheet(row) for row in records]
        if not sheet_repository.save_records(self.worksheet_name, self.columns, rows):
            st.session_state.tasks_fallback = records

    def append(self, task: dict[str, Any], author: str | None = None, account: str | None = None) -> bool:
        return LegacyTaskService.add_task(task, author=author, account=account)

    def query(
        self,
        status: str | None = None,
        assignee: str | None = None,
        category: str | None = None,
        importance: str | None = None,
        urgency: str | None = None,
        due_before: date | str | None = None,
        due_after: date | str | None = None,
        keyword: str | None = None,
    ) -> list[dict]:
        tasks = self.get_all()

        if status:
            tasks = [task for task in tasks if self._match_equal(task.get("status"), status)]

        if assignee:
            tasks = [
                task for task in tasks
                if assignee in ", ".join(map(str, task.get("assignees", [])))
                or assignee in str(task.get("assignee", ""))
            ]

        if category:
            tasks = [task for task in tasks if self._match_equal(task.get("category"), category)]

        if importance:
            tasks = [task for task in tasks if self._match_equal(task.get("importance"), importance)]

        if urgency:
            tasks = [task for task in tasks if self._match_equal(task.get("urgency"), urgency)]

        if due_before:
            before = parse_date(due_before, None)
            if before:
                tasks = [
                    task for task in tasks
                    if parse_date(task.get("due"), None) and parse_date(task.get("due"), None) <= before
                ]

        if due_after:
            after = parse_date(due_after, None)
            if after:
                tasks = [
                    task for task in tasks
                    if parse_date(task.get("due"), None) and parse_date(task.get("due"), None) >= after
                ]

        if keyword:
            key = str(keyword).strip()
            tasks = [
                task for task in tasks
                if key in str(task.get("title", ""))
                or key in str(task.get("notes", ""))
                or key in str(task.get("category", ""))
                or key in str(task.get("tags", ""))
            ]

        return tasks

    def get_by_id(self, task_id: int | str) -> dict | None:
        target = parse_int(task_id, 0)
        for task in self.get_all():
            if parse_int(task.get("id"), 0) == target:
                return task
        return None

    def get_active(self) -> list[dict]:
        return self.query(status="Active")

    def get_completed(self) -> list[dict]:
        return self.query(status="Completed")

    def get_by_assignee(self, assignee: str) -> list[dict]:
        return self.query(assignee=assignee)


task_repository = TaskRepository()
