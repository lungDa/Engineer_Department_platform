from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from config.功能開關 import 要求功能開啟
from services.certificate_service import CertificateService
from services.core import AppInitializer, UserService, current_department


要求功能開啟("證照資料整合")
st.set_page_config(page_title="證照資料整合", layout="wide")
AppInitializer.setup(load_tasks=False, load_meetings=False, load_approvals=False)

st.header("🪪 證照資料整合")
st.caption("集中管理人員證照、複訓與到期日；可指定到期前通知對象及通知方式。")

users = [
    user for user in UserService.get_active_users()
    if str(user.get("department") or "") != "系統獨立"
]
users_by_name = {str(user.get("name") or "").strip(): user for user in users if str(user.get("name") or "").strip()}
all_people = UserService.get_all_partner_names(current_department())


with st.expander("➕ 新增人員證照（所有人皆可使用）", expanded=False):
    certificate_options = list(CertificateService.CERTIFICATE_DEFAULTS)
    certificate_name = st.selectbox(
        "證照名稱 *",
        certificate_options,
        format_func=lambda value: (
            f"{CertificateService.CERTIFICATE_DEFAULTS[value]['category']}｜{value}"
        ),
        help="選擇後會自動帶入預設複訓頻率；當次可修改，但不會改變系統預設值。",
    )
    certificate_default = CertificateService.CERTIFICATE_DEFAULTS[certificate_name]

    with st.form("certificate_add_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            holder_name = st.selectbox("姓名 *", list(users_by_name))
            certificate_number = st.text_input("證書字號")
        with c2:
            issuer = st.text_input("認證單位（以最新複訓單位登錄）")
            retraining_frequency = st.text_input(
                "複訓頻率",
                value=certificate_default["retraining_frequency"],
                key=f"certificate_retraining_{certificate_name}",
                help="這裡的修改只套用本次新增資料，不會改變此證照的預設值。",
            )
            issue_date = st.date_input("發證日期 *", value=date.today())
        with c3:
            has_retraining_date = st.checkbox("已有最近複訓日期")
            retraining_date = st.date_input("最近複訓日期", value=date.today(), disabled=not has_retraining_date)
            expiry_date = st.date_input("到期日期 *", value=date.today())

        st.markdown("##### 到期提醒（可選）")
        notify_enabled = st.checkbox("啟用此筆證照的到期提醒", value=True)
        n1, n2, n3 = st.columns([2, 1, 1])
        with n1:
            notify_people = st.multiselect(
                "被通知者",
                all_people,
                default=[holder_name] if holder_name in all_people else [],
                disabled=not notify_enabled,
            )
        with n2:
            reminder_days = st.number_input("提前通知天數", min_value=1, max_value=365, value=30, disabled=not notify_enabled)
        with n3:
            notify_channels = st.multiselect(
                "通知方式",
                ["Teams", "Outlook", "LINE"],
                default=["Teams", "Outlook", "LINE"],
                disabled=not notify_enabled,
            )
        notes = st.text_area("備註")

        if st.form_submit_button("新增證照資料", type="primary", width="stretch"):
            if not holder_name or not certificate_name:
                st.error("請選擇姓名並填寫證照名稱。")
            elif expiry_date < issue_date:
                st.error("到期日期不可早於發證日期。")
            elif notify_enabled and not notify_people:
                st.error("已啟用提醒，請至少選擇一位被通知者。")
            elif notify_enabled and not notify_channels:
                st.error("已啟用提醒，請至少選擇一種通知方式。")
            else:
                holder = users_by_name[holder_name]
                saved = CertificateService.add({
                    "account": holder.get("account", ""),
                    "name": holder_name,
                    "certificate_name": certificate_name,
                    "certificate_number": certificate_number.strip(),
                    "issuer": issuer.strip(),
                    "retraining_frequency": retraining_frequency.strip(),
                    "issue_date": issue_date,
                    "retraining_date": retraining_date if has_retraining_date else "",
                    "expiry_date": expiry_date,
                    "notify_enabled": notify_enabled,
                    "notify_people": notify_people,
                    "notify_channels": [channel.lower() for channel in notify_channels],
                    "reminder_days": int(reminder_days),
                    "notes": notes.strip(),
                })
                if saved:
                    st.success("證照資料已新增。")
                    st.rerun()
                else:
                    st.error("新增失敗，請檢查 Google Sheet 連線與編輯權限。")


records = CertificateService.load_all()
today = date.today()


def status_text(row: dict) -> str:
    expiry = CertificateService.parse_date(row.get("expiry_date"))
    if not expiry:
        return "未設定"
    days = (expiry - today).days
    reminder = CertificateService.to_int(row.get("reminder_days"), 30)
    if days < 0:
        return f"🔴 已逾期 {-days} 天"
    if days <= reminder:
        return f"🟠 {days} 天後到期"
    return f"🟢 有效（剩 {days} 天）"


def display_row(row: dict) -> dict:
    return {
        "工號": row.get("account", ""),
        "姓名": row.get("name", ""),
        "證照名稱": row.get("certificate_name", ""),
        "證書字號": row.get("certificate_number", ""),
        "認證單位（以最新複訓單位登錄）": row.get("issuer", ""),
        "複訓頻率": row.get("retraining_frequency", ""),
        "發證日期": row.get("issue_date", ""),
        "複訓日期": row.get("retraining_date", ""),
        "到期日期": row.get("expiry_date", ""),
        "到期狀態": status_text(row),
    }


st.divider()
view_col, search_col = st.columns([1, 2])
with view_col:
    view_mode = st.radio(
        "排列方式",
        ["同一證照列出所有名單", "同一人列出所有證照"],
        horizontal=True,
    )
with search_col:
    keyword = st.text_input("搜尋", placeholder="姓名、工號、證照名稱、證書字號或認證單位")

if keyword.strip():
    key = keyword.strip().casefold()
    records = [
        row for row in records
        if any(key in str(row.get(field, "")).casefold() for field in (
            "account", "name", "certificate_name", "certificate_number", "issuer"
        ))
    ]

if not records:
    st.info("目前沒有符合條件的證照資料。")
else:
    group_field = "certificate_name" if view_mode.startswith("同一證照") else "name"
    groups: dict[str, list[dict]] = {}
    for record in records:
        groups.setdefault(str(record.get(group_field) or "未分類"), []).append(record)
    for group_name in sorted(groups):
        group_rows = groups[group_name]
        with st.expander(f"{'🪪' if group_field == 'certificate_name' else '👤'} {group_name}｜{len(group_rows)} 筆", expanded=True):
            rows = [display_row(row) for row in sorted(group_rows, key=lambda item: (str(item.get("expiry_date", "")), str(item.get("name", "")), str(item.get("certificate_name", ""))))]
            column_order = list(rows[0])
            if group_field == "certificate_name":
                column_order.remove("證照名稱")
            st.dataframe(pd.DataFrame(rows)[column_order], hide_index=True, width="stretch")


st.divider()
with st.expander("🗑️ 刪除證照資料（權限 6 以上或品質安全課人員）", expanded=False):
    if not records:
        st.caption("目前沒有可刪除的證照資料。")
    else:
        labels = {
            CertificateService.to_int(row.get("id")): (
                f"{row.get('name', '')}｜{row.get('certificate_name', '')}｜"
                f"{row.get('certificate_number', '') or '無證書字號'}｜到期 {row.get('expiry_date', '')}"
            ) for row in records
        }
        with st.form("certificate_delete_form"):
            record_id = st.selectbox("選擇要刪除的資料", list(labels), format_func=lambda value: labels[value])
            account = st.text_input("操作者工號")
            password = st.text_input("操作者密碼", type="password")
            confirm = st.checkbox("我確認要永久刪除此筆證照資料")
            submitted = st.form_submit_button("刪除證照資料", type="primary", width="stretch")
            if submitted:
                ok, message, operator = UserService.authenticate(account, password)
                if not ok:
                    st.error(message)
                elif not (
                    UserService.effective_role_level(operator) >= 6
                    or UserService.has_department(operator, "品質安全課")
                ):
                    st.error("權限不足：僅限權限 6 以上或品質安全課人員刪除。")
                elif not confirm:
                    st.error("請先勾選刪除確認。")
                elif CertificateService.delete(record_id):
                    st.success("證照資料已刪除。")
                    st.rerun()
                else:
                    st.error("刪除失敗，請檢查 Google Sheet 連線與編輯權限。")
