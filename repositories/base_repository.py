from abc import ABC
from typing import Any

from shared.logger import get_logger


class BaseRepository(ABC):
    """Base repository with common query/filter helpers."""

    repository_name = "base"

    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)

    @staticmethod
    def _match_text(value: Any, target: str | None) -> bool:
        if target in (None, ""):
            return True
        return str(target).strip() in str(value or "")

    @staticmethod
    def _match_equal(value: Any, target: Any | None) -> bool:
        if target in (None, ""):
            return True
        return str(value or "").strip() == str(target).strip()
