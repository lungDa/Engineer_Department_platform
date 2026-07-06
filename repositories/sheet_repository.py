from typing import Any

from repositories.base_repository import BaseRepository
from services.sheet_db import SheetDB


class SheetRepository(BaseRepository):
    """Low-level repository around SheetDB.

    SheetDB already handles Google Sheet connection, Streamlit cache,
    worksheet creation, normalization, and diagnostics.
    """

    repository_name = "sheet"

    def is_connected(self) -> bool:
        return SheetDB.spreadsheet() is not None

    def load_records(
        self,
        worksheet_name: str,
        columns: list[str],
        default_rows: list[dict] | None = None,
    ) -> list[dict]:
        records = SheetDB.load(worksheet_name, columns, default_rows or [])
        return records if records is not None else (default_rows or [])

    def save_records(self, worksheet_name: str, columns: list[str], records: list[dict]) -> bool:
        normalized = SheetDB.normalize_records(records, columns)
        return bool(SheetDB.save(worksheet_name, columns, normalized))

    def append_record(self, worksheet_name: str, columns: list[str], record: dict[str, Any]) -> bool:
        return bool(SheetDB.append(worksheet_name, columns, record))

    def normalize_records(self, records: list[dict], columns: list[str]) -> list[dict]:
        return SheetDB.normalize_records(records, columns)

    def clear_cache(self) -> None:
        SheetDB.clear_cache()


sheet_repository = SheetRepository()
