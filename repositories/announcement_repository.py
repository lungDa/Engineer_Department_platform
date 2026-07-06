from datetime import date

import streamlit as st

from repositories.base_repository import BaseRepository
from repositories.sheet_repository import sheet_repository
from services.core import AnnouncementService as LegacyAnnouncementService, bool_text, parse_date, parse_int


class AnnouncementRepository(BaseRepository):
    """Repository for Announcements worksheet."""

    repository_name = "announcement"

    worksheet_name = LegacyAnnouncementService.WORKSHEET_NAME
    columns = LegacyAnnouncementService.COLUMNS

    def get_all(self) -> list[dict]:
        records = sheet_repository.load_records(self.worksheet_name, self.columns, [])
        return records if records is not None else st.session_state.get("announcements_fallback", [])

    def save_all(self, records: list[dict]) -> bool:
        records = sheet_repository.normalize_records(records, self.columns)
        ok = sheet_repository.save_records(self.worksheet_name, self.columns, records)
        if not ok:
            st.session_state.announcements_fallback = records
        return ok

    def get_active(self) -> list[dict]:
        today = date.today()
        active = []
        for ann in self.get_all():
            if bool_text(ann.get("active", "TRUE")) == "FALSE":
                continue
            expires_at = parse_date(ann.get("expires_at", ""), None)
            if expires_at and expires_at < today:
                continue
            active.append(ann)
        return sorted(
            active,
            key=lambda a: (
                bool_text(a.get("pinned", "FALSE"), False) != "TRUE",
                -parse_int(a.get("id", 0), 0),
            ),
        )

    def query(self, active_only: bool = False, keyword: str | None = None, level: str | None = None) -> list[dict]:
        rows = self.get_active() if active_only else self.get_all()

        if keyword:
            key = str(keyword).strip()
            rows = [
                row for row in rows
                if key in str(row.get("title", ""))
                or key in str(row.get("content", ""))
                or key in str(row.get("author", ""))
            ]

        if level:
            rows = [row for row in rows if str(row.get("level", "")).strip() == str(level).strip()]

        return rows


announcement_repository = AnnouncementRepository()
