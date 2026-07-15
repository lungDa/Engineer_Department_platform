import json
import os
import time
import traceback
from typing import Any

import streamlit as st


@st.cache_resource(show_spinner=False)
def _cached_spreadsheet(sheet_id: str, service_account_json: str):
    """Create and cache a gspread Spreadsheet object.

    The caller passes primitive strings only, so Streamlit can cache safely.
    Exceptions are intentionally not swallowed here; SheetDB.spreadsheet()
    catches them and stores full diagnostics for the UI.
    """
    import gspread
    from google.oauth2.service_account import Credentials

    info = json.loads(service_account_json)
    credentials = Credentials.from_service_account_info(
        info,
        scopes=SheetDB.SCOPES,
    )
    client = gspread.authorize(credentials)
    return client.open_by_key(sheet_id)


@st.cache_data(ttl=30, show_spinner=False)
def _cached_sheet_records(name: str, columns_json: str, default_rows_json: str, cache_version: int):
    """Read and cache one worksheet for a short time.

    Google Sheet is the slowest part of the app.  This cache reduces repeated
    API reads during one Streamlit rerun/page switch while still refreshing
    automatically within 30 seconds.  cache_version is increased after writes
    so new data appears immediately after append/save/update operations.
    """
    columns = json.loads(columns_json)
    default_rows = json.loads(default_rows_json) if default_rows_json else None

    ws = SheetDB.worksheet(name, columns, default_rows)
    if not ws:
        return None

    records = SheetDB.get_records(ws, columns)
    if not records and default_rows:
        SheetDB.save(name, columns, default_rows)
        records = default_rows
    return SheetDB.normalize_records(records, columns)


@st.cache_data(ttl=30, show_spinner=False)
def _cached_sheet_bundle(specs_json: str, cache_version: int):
    """Read multiple worksheets with one Google Sheets batch request."""
    specs = json.loads(specs_json)
    spreadsheet = SheetDB.spreadsheet()
    if not spreadsheet:
        return {}
    ranges = [f"'{item['name'].replace(chr(39), chr(39)*2)}'!A:ZZ" for item in specs]
    response = spreadsheet.values_batch_get(ranges)
    value_ranges = response.get("valueRanges", []) if isinstance(response, dict) else []
    result = {}
    for item, payload in zip(specs, value_ranges):
        columns = item["columns"]
        values = payload.get("values", []) if isinstance(payload, dict) else []
        if not values:
            result[item["name"]] = []
            continue
        header = [str(v).strip() for v in values[0]]
        index_map = {col: header.index(col) for col in columns if col in header}
        rows = []
        for raw in values[1:]:
            row = {col: (raw[idx] if idx < len(raw) else "") for col, idx in index_map.items()}
            row = {col: row.get(col, "") for col in columns}
            if any(str(v).strip() for v in row.values()):
                rows.append(row)
        result[item["name"]] = SheetDB.normalize_records(rows, columns)
    return result


class SheetDB:
    # V3.4 Enterprise Turbo Edition
    # 依工作表用途分層快取：慢變資料拉長 TTL，熱資料縮短 TTL。
    # 這一層是 session cache，會先擋掉同一位使用者換頁/重跑造成的重複 Google API 讀取。
    SHEET_TTL_SECONDS = {
        "Users": 600,
        "Categories": 1800,
        "Tags": 1800,
        "Tasks": 5,
        "Announcements": 10,
        "Meetings": 10,
        "Approvals": 10,
    }

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    @staticmethod
    def _set_error(message: str):
        st.session_state["sheet_db_connected"] = False
        st.session_state["sheet_db_error"] = message
        return None

    @staticmethod
    def _plain(value):
        """Convert Streamlit secrets AttrDict / nested objects into plain dicts."""
        if value is None:
            return None
        if isinstance(value, dict):
            return {k: SheetDB._plain(v) for k, v in value.items()}
        try:
            return {k: SheetDB._plain(v) for k, v in dict(value).items()}
        except Exception:
            return value

    @staticmethod
    def _normalize_private_key(info: dict | None) -> dict | None:
        if not info:
            return None
        info = dict(info)
        key = str(info.get("private_key", "") or "").strip()
        if key:
            # Streamlit TOML sometimes contains literal \n copied from JSON.
            key = key.replace("\\n", "\n")
            # If user pasted only the MII... body, recover PEM wrapper.
            if "-----BEGIN PRIVATE KEY-----" not in key and key.startswith("MII"):
                key = "-----BEGIN PRIVATE KEY-----\n" + key + "\n-----END PRIVATE KEY-----\n"
            if not key.endswith("\n"):
                key += "\n"
            info["private_key"] = key
        return info

    @staticmethod
    def get_sheet_id():
        """Read spreadsheet id from several supported configurations."""
        try:
            if "SHEET_ID" in st.secrets and str(st.secrets.get("SHEET_ID", "")).strip():
                return str(st.secrets.get("SHEET_ID")).strip()

            if "SPREADSHEET_ID" in st.secrets and str(st.secrets.get("SPREADSHEET_ID", "")).strip():
                return str(st.secrets.get("SPREADSHEET_ID")).strip()

            if "google_sheet" in st.secrets:
                gs = SheetDB._plain(st.secrets.get("google_sheet")) or {}
                value = gs.get("spreadsheet_id") or gs.get("SHEET_ID") or gs.get("spreadsheet")
                if value:
                    return str(value).strip()

            if "connections" in st.secrets:
                connections = SheetDB._plain(st.secrets.get("connections")) or {}
                gsheets = connections.get("gsheets", {}) or {}
                value = gsheets.get("spreadsheet") or gsheets.get("spreadsheet_id") or gsheets.get("SHEET_ID")
                if value:
                    return str(value).strip()

            env_value = os.getenv("SHEET_ID") or os.getenv("SPREADSHEET_ID")
            if env_value:
                return str(env_value).strip()

            return None
        except Exception as e:
            SheetDB._set_error(f"讀取 SHEET_ID 失敗：{e}")
            return None

    @staticmethod
    def get_service_account_info():
        """Read service account info from supported Streamlit Secrets shapes."""
        try:
            if "gcp_service_account" in st.secrets:
                info = SheetDB._plain(st.secrets.get("gcp_service_account"))
                return SheetDB._normalize_private_key(info)

            if "connections" in st.secrets:
                connections = SheetDB._plain(st.secrets.get("connections")) or {}
                gsheets = connections.get("gsheets", {}) or {}
                required = ["type", "project_id", "private_key_id", "private_key", "client_email", "client_id"]
                if all(gsheets.get(k) for k in required):
                    info = {
                        "type": gsheets.get("type"),
                        "project_id": gsheets.get("project_id"),
                        "private_key_id": gsheets.get("private_key_id"),
                        "private_key": gsheets.get("private_key"),
                        "client_email": gsheets.get("client_email"),
                        "client_id": gsheets.get("client_id"),
                        "auth_uri": gsheets.get("auth_uri", "https://accounts.google.com/o/oauth2/auth"),
                        "token_uri": gsheets.get("token_uri", "https://oauth2.googleapis.com/token"),
                        "auth_provider_x509_cert_url": gsheets.get("auth_provider_x509_cert_url", "https://www.googleapis.com/oauth2/v1/certs"),
                        "client_x509_cert_url": gsheets.get("client_x509_cert_url", ""),
                        "universe_domain": gsheets.get("universe_domain", "googleapis.com"),
                    }
                    return SheetDB._normalize_private_key(info)

            required = ["type", "project_id", "private_key_id", "private_key", "client_email", "client_id"]
            if all(k in st.secrets and st.secrets.get(k) for k in required):
                info = {
                    "type": st.secrets.get("type"),
                    "project_id": st.secrets.get("project_id"),
                    "private_key_id": st.secrets.get("private_key_id"),
                    "private_key": st.secrets.get("private_key"),
                    "client_email": st.secrets.get("client_email"),
                    "client_id": st.secrets.get("client_id"),
                    "auth_uri": st.secrets.get("auth_uri", "https://accounts.google.com/o/oauth2/auth"),
                    "token_uri": st.secrets.get("token_uri", "https://oauth2.googleapis.com/token"),
                    "auth_provider_x509_cert_url": st.secrets.get("auth_provider_x509_cert_url", "https://www.googleapis.com/oauth2/v1/certs"),
                    "client_x509_cert_url": st.secrets.get("client_x509_cert_url", ""),
                    "universe_domain": st.secrets.get("universe_domain", "googleapis.com"),
                }
                return SheetDB._normalize_private_key(info)

            return None
        except Exception as e:
            SheetDB._set_error(f"讀取 Service Account 失敗：{e}")
            return None

    @staticmethod
    def _validate_service_account(info: dict | None) -> tuple[bool, str]:
        if not info:
            return False, "找不到 gcp_service_account。請在 Secrets 加入 [gcp_service_account] 區塊。"
        required = [
            "type", "project_id", "private_key_id", "private_key", "client_email", "client_id",
            "auth_uri", "token_uri", "auth_provider_x509_cert_url", "client_x509_cert_url",
        ]
        missing = [k for k in required if not info.get(k)]
        if missing:
            return False, "Service Account 欄位缺少：" + ", ".join(missing)
        key = str(info.get("private_key", ""))
        if "-----BEGIN PRIVATE KEY-----" not in key or "-----END PRIVATE KEY-----" not in key:
            return False, "private_key 不是有效 PEM 格式，請確認 BEGIN/END PRIVATE KEY 是否存在。"
        return True, ""

    @staticmethod
    def spreadsheet():
        """Return gspread Spreadsheet object or None, with full diagnostics."""
        sheet_id = SheetDB.get_sheet_id()
        service_account_info = SheetDB.get_service_account_info()

        if not sheet_id:
            return SheetDB._set_error("找不到 SHEET_ID。請在 Streamlit Secrets 設定 SHEET_ID。")

        ok, message = SheetDB._validate_service_account(service_account_info)
        if not ok:
            return SheetDB._set_error(message)

        try:
            service_account_json = json.dumps(
                SheetDB._normalize_private_key(service_account_info),
                ensure_ascii=False,
                sort_keys=True,
            )
            spreadsheet = _cached_spreadsheet(str(sheet_id).strip(), service_account_json)
            st.session_state["sheet_db_connected"] = True
            st.session_state["sheet_db_title"] = getattr(spreadsheet, "title", "")
            st.session_state["sheet_db_error"] = ""
            return spreadsheet
        except Exception as e:
            error_type = type(e).__name__
            full = traceback.format_exc()
            hint = ""
            text = str(e)
            if "SpreadsheetNotFound" in full or "not found" in text.lower():
                hint = "\n\n可能原因：SHEET_ID 錯誤，或 Google Sheet 尚未分享給 Service Account。"
            elif "This operation is not supported for this document" in text:
                hint = "\n\n可能原因：這份文件仍是 Office Excel 檔，請另存為 Google 試算表。"
            elif "403" in text or "Permission" in text:
                hint = "\n\n可能原因：Google Sheet 沒有分享編輯權限給 Service Account。"
            elif "PEM" in text or "private_key" in text:
                hint = "\n\n可能原因：private_key 格式錯誤，請檢查 Streamlit Secrets。"
            return SheetDB._set_error(f"{error_type}: {e}{hint}\n\n--- traceback ---\n{full}")

    @staticmethod
    def clear_cache(sheet_name: str | None = None):
        try:
            _cached_spreadsheet.clear()
        except Exception:
            pass
        try:
            _cached_sheet_records.clear()
        except Exception:
            pass

        if sheet_name:
            st.session_state.pop(SheetDB.session_cache_key(sheet_name), None)
        else:
            for key in list(st.session_state.keys()):
                if str(key).startswith("sheet_db_session_cache__"):
                    st.session_state.pop(key, None)

        st.session_state["sheet_db_cache_version"] = st.session_state.get("sheet_db_cache_version", 0) + 1
        st.session_state.pop("sheet_db_error", None)
        st.session_state.pop("sheet_db_connected", None)
        st.session_state.pop("sheet_db_title", None)

    @staticmethod
    def cache_version() -> int:
        return int(st.session_state.get("sheet_db_cache_version", 0))

    @staticmethod
    def bump_cache_version(sheet_name: str | None = None):
        st.session_state["sheet_db_cache_version"] = SheetDB.cache_version() + 1
        try:
            _cached_sheet_records.clear()
        except Exception:
            pass
        if sheet_name:
            st.session_state.pop(SheetDB.session_cache_key(sheet_name), None)
        else:
            for key in list(st.session_state.keys()):
                if str(key).startswith("sheet_db_session_cache__"):
                    st.session_state.pop(key, None)

    @staticmethod
    def session_cache_key(name: str) -> str:
        return f"sheet_db_session_cache__{name}"

    @staticmethod
    def sheet_ttl(name: str) -> int:
        return int(SheetDB.SHEET_TTL_SECONDS.get(name, 30))

    @staticmethod
    def get_session_cached(name: str, cache_version: int):
        payload = st.session_state.get(SheetDB.session_cache_key(name))
        if not payload:
            return None
        if payload.get("version") != cache_version:
            return None
        ttl = SheetDB.sheet_ttl(name)
        if time.time() - float(payload.get("stored_at", 0)) > ttl:
            return None
        return payload.get("records")

    @staticmethod
    def set_session_cached(name: str, records):
        st.session_state[SheetDB.session_cache_key(name)] = {
            "version": SheetDB.cache_version(),
            "stored_at": time.time(),
            "records": records,
        }

    @staticmethod
    def prefetch(specs: list[tuple[str, list[str], list[dict[str, Any]] | None]]) -> None:
        """Warm session caches for several worksheets in a single HTTP request."""
        missing = []
        version = SheetDB.cache_version()
        for name, columns, default_rows in specs:
            if SheetDB.get_session_cached(name, version) is None:
                missing.append({"name": name, "columns": columns, "default_rows": default_rows or []})
        if not missing:
            return
        try:
            bundle = _cached_sheet_bundle(json.dumps(missing, ensure_ascii=False, default=str), version)
            for item in missing:
                records = bundle.get(item["name"])
                if records is not None:
                    SheetDB.set_session_cached(item["name"], records or item["default_rows"])
        except Exception:
            # Individual SheetDB.load calls remain the compatibility fallback.
            return

    @staticmethod
    def using_google_sheet() -> bool:
        return SheetDB.spreadsheet() is not None

    @staticmethod
    def worksheet(name: str, columns: list[str], default_rows: list[dict[str, Any]] | None = None):
        spreadsheet = SheetDB.spreadsheet()
        if not spreadsheet:
            return None

        try:
            ws = spreadsheet.worksheet(name)
        except Exception:
            try:
                ws = spreadsheet.add_worksheet(title=name, rows=500, cols=max(len(columns), 10))
                ws.append_row(columns)
                if default_rows:
                    ws.append_rows([
                        [SheetDB.to_sheet_value(row.get(col, "")) for col in columns]
                        for row in default_rows
                    ])
                return ws
            except Exception as e:
                return SheetDB._set_error(f"建立工作表 {name} 失敗：{type(e).__name__}: {e}\n{traceback.format_exc()}")

        try:
            header = [str(h).strip() for h in ws.row_values(1)]
            non_empty_header = [h for h in header if h]
            if not non_empty_header:
                SheetDB.update_values(ws, "A1", [columns])
            else:
                missing = [c for c in columns if c not in non_empty_header]
                if missing:
                    SheetDB.update_values(ws, "A1", [non_empty_header + missing])
        except Exception as e:
            SheetDB._set_error(f"檢查工作表 {name} 表頭失敗：{type(e).__name__}: {e}")
        return ws

    @staticmethod
    def update_values(ws, range_name: str, values: list[list[Any]]):
        try:
            return ws.update(values=values, range_name=range_name)
        except TypeError:
            return ws.update(range_name, values)

    @staticmethod
    def get_records(ws, columns: list[str]) -> list[dict[str, Any]]:
        values = ws.get_all_values()
        if not values:
            return []
        header = [str(h).strip() for h in values[0]]
        index_map = {col: header.index(col) for col in columns if col in header}
        records = []
        for raw in values[1:]:
            row = {}
            has_data = False
            for col in columns:
                idx = index_map.get(col)
                val = raw[idx] if idx is not None and idx < len(raw) else ""
                row[col] = val
                if str(val).strip():
                    has_data = True
            if has_data:
                records.append(row)
        return records

    @staticmethod
    def to_sheet_value(value: Any) -> str:
        from datetime import date, datetime
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M")
        if isinstance(value, date):
            return value.strftime("%Y-%m-%d")
        if value is None:
            return ""
        return str(value)

    @staticmethod
    def normalize_records(records: list[dict[str, Any]], columns: list[str]) -> list[dict[str, Any]]:
        return [{col: row.get(col, "") for col in columns} for row in records]

    @staticmethod
    def load(name: str, columns: list[str], default_rows: list[dict[str, Any]] | None = None, force_refresh: bool = False) -> list[dict[str, Any]] | None:
        try:
            version = SheetDB.cache_version()
            if not force_refresh:
                session_records = SheetDB.get_session_cached(name, version)
                if session_records is not None:
                    return session_records

            columns_json = json.dumps(columns, ensure_ascii=False)
            default_rows_json = json.dumps(default_rows or [], ensure_ascii=False, default=str)
            records = _cached_sheet_records(
                name,
                columns_json,
                default_rows_json,
                version,
            )
            if records is not None:
                SheetDB.set_session_cached(name, records)
            return records
        except Exception as e:
            SheetDB._set_error(f"讀取工作表 {name} 失敗：{type(e).__name__}: {e}\n{traceback.format_exc()}")
            return None

    @staticmethod
    def save(name: str, columns: list[str], records: list[dict[str, Any]]) -> bool:
        ws = SheetDB.worksheet(name, columns)
        if not ws:
            return False
        try:
            normalized = SheetDB.normalize_records(records, columns)
            values = [columns]
            values.extend([
                [SheetDB.to_sheet_value(row.get(col, "")) for col in columns]
                for row in normalized
            ])
            ws.clear()
            SheetDB.update_values(ws, "A1", values)
            SheetDB.bump_cache_version(name)
            return True
        except Exception as e:
            SheetDB._set_error(f"寫入工作表 {name} 失敗：{type(e).__name__}: {e}\n{traceback.format_exc()}")
            return False

    @staticmethod
    def append(name: str, columns: list[str], record: dict[str, Any]) -> bool:
        ws = SheetDB.worksheet(name, columns)
        if not ws:
            return False
        try:
            row = {col: record.get(col, "") for col in columns}
            ws.append_row([SheetDB.to_sheet_value(row.get(col, "")) for col in columns])
            SheetDB.bump_cache_version(name)
            return True
        except Exception as e:
            SheetDB._set_error(f"追加工作表 {name} 失敗：{type(e).__name__}: {e}\n{traceback.format_exc()}")
            return False


class SheetDiagnostics:
    @staticmethod
    def status(force_retest: bool = False) -> dict:
        if force_retest:
            SheetDB.clear_cache()

        sheet_id = SheetDB.get_sheet_id()
        info = SheetDB.get_service_account_info()
        client_email = (info or {}).get("client_email", "")
        service_ok, service_error = SheetDB._validate_service_account(info)

        ss = None
        if sheet_id and service_ok:
            ss = SheetDB.spreadsheet()
        elif not sheet_id:
            SheetDB._set_error("找不到 SHEET_ID。")
        elif not service_ok:
            SheetDB._set_error(service_error)

        return {
            "sheet_id_present": bool(sheet_id),
            "sheet_id": str(sheet_id or ""),
            "service_account_present": bool(info),
            "service_account_valid": bool(service_ok),
            "client_email": client_email,
            "connected": ss is not None,
            "spreadsheet_title": st.session_state.get("sheet_db_title", ""),
            "error": st.session_state.get("sheet_db_error", ""),
        }
