import json
import os
from typing import Any

import streamlit as st

@st.cache_resource(show_spinner=False)
def _cached_spreadsheet(sheet_id: str, service_account_json: str):
    import gspread
    from google.oauth2.service_account import Credentials

    info = json.loads(service_account_json)
    credentials = Credentials.from_service_account_info(
        info,
        scopes=SheetDB.SCOPES,
    )
    client = gspread.authorize(credentials)
    return client.open_by_key(sheet_id)


class SheetDB:
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    @staticmethod
    def _plain(value):
        """把 Streamlit Secrets 的 AttrDict / 巢狀物件轉成一般 dict。"""
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
            # Streamlit TOML 若直接貼 JSON，常會保留文字 \n；這裡統一轉成真正換行。
            key = key.replace("\\n", "\n")
            # 若只貼中間 MII... 內容，嘗試自動補 PEM Header/Footer。
            if "-----BEGIN PRIVATE KEY-----" not in key and key.startswith("MII"):
                key = "-----BEGIN PRIVATE KEY-----\n" + key + "\n-----END PRIVATE KEY-----\n"
            if not key.endswith("\n"):
                key += "\n"
            info["private_key"] = key
        return info

    @staticmethod
    def get_sheet_id():
        try:
            # 支援：SHEET_ID = "..."
            if "SHEET_ID" in st.secrets and str(st.secrets.get("SHEET_ID", "")).strip():
                return str(st.secrets.get("SHEET_ID")).strip()

            # 支援：SPREADSHEET_ID = "..."
            if "SPREADSHEET_ID" in st.secrets and str(st.secrets.get("SPREADSHEET_ID", "")).strip():
                return str(st.secrets.get("SPREADSHEET_ID")).strip()

            # 支援：[google_sheet] spreadsheet_id = "..."
            if "google_sheet" in st.secrets:
                gs = SheetDB._plain(st.secrets.get("google_sheet")) or {}
                value = gs.get("spreadsheet_id") or gs.get("SHEET_ID") or gs.get("spreadsheet")
                if value:
                    return str(value).strip()

            # 支援：[connections.gsheets] spreadsheet = "..."
            if "connections" in st.secrets:
                connections = SheetDB._plain(st.secrets.get("connections")) or {}
                gsheets = connections.get("gsheets", {}) or {}
                value = gsheets.get("spreadsheet") or gsheets.get("spreadsheet_id") or gsheets.get("SHEET_ID")
                if value:
                    return str(value).strip()

            env_value = os.getenv("SHEET_ID") or os.getenv("SPREADSHEET_ID")
            if env_value:
                return str(env_value).strip()

            st.session_state["sheet_db_error"] = "找不到 SHEET_ID。請在 Streamlit Secrets 設定 SHEET_ID。"
            return None
        except Exception as e:
            st.session_state["sheet_db_error"] = f"讀取 SHEET_ID 失敗：{e}"
            return None

    @staticmethod
    def get_service_account_info():
        try:
            # 推薦格式：[gcp_service_account]
            if "gcp_service_account" in st.secrets:
                info = SheetDB._plain(st.secrets.get("gcp_service_account"))
                return SheetDB._normalize_private_key(info)

            # Streamlit 內建格式：[connections.gsheets]
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

            # 平面格式：type/project_id/private_key... 直接放最外層
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

            st.session_state["sheet_db_error"] = "找不到 gcp_service_account。請在 Secrets 加入 [gcp_service_account] 區塊。"
            return None
        except Exception as e:
            st.session_state["sheet_db_error"] = f"讀取 Service Account 失敗：{e}"
            return None

    @staticmethod
    def spreadsheet():
        try:
            sheet_id = SheetDB.get_sheet_id()
            service_account_info = SheetDB.get_service_account_info()

            if not sheet_id:
                st.session_state.setdefault("sheet_db_error", "找不到 SHEET_ID。")
                return None
            if not service_account_info:
                st.session_state.setdefault("sheet_db_error", "找不到 Google Service Account 設定。")
                return None

            service_account_json = json.dumps(
                SheetDB._normalize_private_key(service_account_info),
                ensure_ascii=False,
                sort_keys=True,
            )
            spreadsheet = _cached_spreadsheet(str(sheet_id).strip(), service_account_json)
            st.session_state["sheet_db_connected"] = True
            st.session_state["sheet_db_title"] = getattr(spreadsheet, "title", "")
            st.session_state.pop("sheet_db_error", None)
            return spreadsheet
        except Exception as e:
            st.session_state["sheet_db_connected"] = False
            st.session_state["sheet_db_error"] = str(e)
            return None

    @staticmethod
    def clear_cache():
        try:
            _cached_spreadsheet.clear()
        except Exception:
            pass
        st.session_state.pop("sheet_db_error", None)
        st.session_state.pop("sheet_db_connected", None)
        st.session_state.pop("sheet_db_title", None)

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
                st.session_state["sheet_db_error"] = f"建立工作表 {name} 失敗：{e}"
                return None

        # 表頭空白時補上欄位；表頭缺欄時向右補齊，不刪既有資料。
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
            st.session_state["sheet_db_error"] = f"檢查工作表 {name} 表頭失敗：{e}"
        return ws

    @staticmethod
    def update_values(ws, range_name: str, values: list[list[Any]]):
        """gspread v5/v6 相容更新，避免 Worksheet.update 參數順序錯誤。"""
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
    def load(name: str, columns: list[str], default_rows: list[dict[str, Any]] | None = None) -> list[dict[str, Any]] | None:
        ws = SheetDB.worksheet(name, columns, default_rows)
        if not ws:
            return None
        try:
            records = SheetDB.get_records(ws, columns)
            if not records and default_rows:
                SheetDB.save(name, columns, default_rows)
                records = default_rows
            return SheetDB.normalize_records(records, columns)
        except Exception as e:
            st.session_state["sheet_db_error"] = f"讀取工作表 {name} 失敗：{e}"
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
            return True
        except Exception as e:
            st.session_state["sheet_db_error"] = f"寫入工作表 {name} 失敗：{e}"
            return False

    @staticmethod
    def append(name: str, columns: list[str], record: dict[str, Any]) -> bool:
        ws = SheetDB.worksheet(name, columns)
        if not ws:
            return False
        try:
            row = {col: record.get(col, "") for col in columns}
            ws.append_row([SheetDB.to_sheet_value(row.get(col, "")) for col in columns])
            return True
        except Exception as e:
            st.session_state["sheet_db_error"] = f"追加工作表 {name} 失敗：{e}"
            return False



class SheetDiagnostics:
    @staticmethod
    def status() -> dict:
        sheet_id = SheetDB.get_sheet_id()
        info = SheetDB.get_service_account_info()
        ss = SheetDB.spreadsheet()
        return {
            "sheet_id_present": bool(sheet_id),
            "sheet_id": str(sheet_id or ""),
            "service_account_present": bool(info),
            "client_email": (info or {}).get("client_email", ""),
            "connected": ss is not None,
            "spreadsheet_title": st.session_state.get("sheet_db_title", ""),
            "error": st.session_state.get("sheet_db_error", ""),
        }
