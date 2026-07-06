from typing import Any

from repositories.sheet_repository import sheet_repository
from services.base_service import BaseService


class SheetService(BaseService):
    """Google Sheet service facade using Repository Layer."""

    service_name = "sheet"

    def is_connected(self) -> bool:
        return sheet_repository.is_connected()

    def load_records(self, worksheet_name: str, columns: list[str], default_rows: list[dict] | None = None) -> list[dict]:
        return sheet_repository.load_records(worksheet_name, columns, default_rows or [])

    def save_records(self, worksheet_name: str, columns: list[str], records: list[dict]) -> bool:
        return sheet_repository.save_records(worksheet_name, columns, records)

    def append_record(self, worksheet_name: str, columns: list[str], record: dict[str, Any]) -> bool:
        return sheet_repository.append_record(worksheet_name, columns, record)

    def normalize_records(self, records: list[dict], columns: list[str]) -> list[dict]:
        return sheet_repository.normalize_records(records, columns)

    def clear_cache(self) -> None:
        sheet_repository.clear_cache()


sheet_service = SheetService()
