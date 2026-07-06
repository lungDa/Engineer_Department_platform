from typing import Any

import streamlit as st

from repositories.base_repository import BaseRepository
from repositories.sheet_repository import sheet_repository
from services.core import UserService as LegacyUserService, bool_text, parse_int


class UserRepository(BaseRepository):
    """Repository for Users worksheet."""

    repository_name = "user"

    worksheet_name = LegacyUserService.WORKSHEET_NAME
    columns = LegacyUserService.COLUMNS

    def default_rows(self) -> list[dict]:
        return LegacyUserService.default_users()

    def get_all(self) -> list[dict]:
        records = sheet_repository.load_records(
            self.worksheet_name,
            self.columns,
            self.default_rows(),
        )
        return records if records is not None else st.session_state.get("user_records_fallback", self.default_rows())

    def save_all(self, records: list[dict]) -> None:
        records = sheet_repository.normalize_records(records, self.columns)
        if not sheet_repository.save_records(self.worksheet_name, self.columns, records):
            st.session_state.user_records_fallback = records

    def query(
        self,
        active: bool | None = None,
        role: str | None = None,
        account: str | None = None,
        name: str | None = None,
    ) -> list[dict]:
        users = self.get_all()

        if active is not None:
            target = "TRUE" if active else "FALSE"
            users = [user for user in users if bool_text(user.get("active", "TRUE")) == target]

        if role:
            users = [user for user in users if role in str(user.get("role", ""))]

        if account:
            users = [
                user for user in users
                if str(user.get("account", "")).strip().lower() == str(account).strip().lower()
            ]

        if name:
            users = [user for user in users if name in str(user.get("name", ""))]

        return users

    def get_active(self) -> list[dict]:
        return self.query(active=True)

    def get_by_account(self, account: str) -> dict | None:
        rows = self.query(account=account)
        return rows[0] if rows else None

    def get_by_name(self, name: str) -> dict | None:
        rows = self.query(name=name)
        return rows[0] if rows else None

    def get_partner_names(self) -> list[str]:
        names = []
        seen = set()
        for user in self.get_active():
            name = str(user.get("name", "")).strip()
            if name and name not in seen:
                seen.add(name)
                names.append(name)
        return sorted(names)

    def is_developer_user(self, user: dict[str, Any] | None) -> bool:
        if not user:
            return False
        if bool_text(user.get("active", "TRUE")) != "TRUE":
            return False
        account = str(user.get("account", "")).strip().lower()
        role = str(user.get("role", "")).strip().lower()
        role_level = parse_int(user.get("role_level", 0), 0)
        return (
            account in {"developer", "dev"}
            or "開發" in role
            or "developer" in role
            or role == "dev"
            or role_level >= 9
        )


user_repository = UserRepository()
