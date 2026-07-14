import pandas as pd
import streamlit as st

from config.departments import DEPARTMENTS
from config.roles import ROLE_LEVELS
from utils import AppInitializer, UserService


st.set_page_config(page_title="人員名單｜課別分類", layout="wide")
AppInitializer.setup(load_tasks=False, load_meetings=False, load_approvals=False)

st.header("👥 人員名單｜課別分類")
st.caption("人員資料依課別獨立整理；停用帳號不會出現在一般人員名單。")

developer_unlocked = st.session_state.get("developer_diagnostics_unlocked", False)
if developer_unlocked:
    st.success("🔓 開發者模式已啟用：可以新增、修改、停用或刪除人員。")
else:
    st.info("🔒 目前為唯讀模式。如需新增或修改人員，請先回首頁按「🛠️ 開發者」並輸入開發者密碼。")

all_users = UserService.get_active_users()
keyword = st.text_input("🔍 搜尋人員", placeholder="輸入姓名、帳號或角色")

summary_cols = st.columns(4)
summary_cols[0].metric("課別總數", len(DEPARTMENTS))
summary_cols[1].metric("啟用人員", len(all_users))
summary_cols[2].metric(
    "目前課別人數",
    len(UserService.get_users_by_department(st.session_state.current_department)),
)
summary_cols[3].metric("目前課別", st.session_state.current_department)

st.divider()

for department in DEPARTMENTS:
    users = UserService.get_users_by_department(department)
    if keyword.strip():
        key = keyword.strip().lower()
        users = [
            user for user in users
            if key in str(user.get("name", "")).lower()
            or key in str(user.get("account", "")).lower()
            or key in str(user.get("role", "")).lower()
        ]

    with st.expander(f"🏢 {department}　｜　{len(users)} 人", expanded=department == st.session_state.current_department):
        if not users:
            st.info("此課別目前沒有符合條件的啟用人員。")
            continue

        rows = [
            {
                "課別": department,
                "姓名": user.get("name", ""),
                "帳號／工號": user.get("account", ""),
                "角色": user.get("role", "一般人員"),
            }
            for user in sorted(users, key=lambda item: str(item.get("name", "")))
        ]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


if developer_unlocked:
    st.divider()
    st.subheader("🛠️ 開發者｜人員名單管理")
    st.caption("此區只會在首頁完成開發者密碼驗證後顯示。")

    manage_department = st.selectbox(
        "管理課別",
        DEPARTMENTS,
        index=DEPARTMENTS.index(st.session_state.current_department),
        key="personnel_manage_department",
    )
    department_users = UserService.get_users_by_department(manage_department, active_only=False)

    edit_mode = st.radio("管理動作", ["新增人員", "修改既有人員"], horizontal=True)
    selected_user = None
    if edit_mode == "修改既有人員":
        if department_users:
            user_options = {
                f"{user.get('name', '')}（{user.get('account', '')}）": user
                for user in department_users
            }
            selected_label = st.selectbox("選擇要修改的人員", list(user_options.keys()))
            selected_user = user_options[selected_label]
        else:
            st.warning("此課別目前沒有人員可修改，請改用新增人員。")

    can_edit = edit_mode == "新增人員" or selected_user is not None
    if can_edit:
        initial_role = str((selected_user or {}).get("role") or "一般人員")
        if initial_role not in ROLE_LEVELS:
            initial_role = "一般人員"
        initial_department = str((selected_user or {}).get("department") or manage_department)
        if initial_department not in DEPARTMENTS:
            initial_department = manage_department

        form_key = f"personnel_editor_{edit_mode}_{(selected_user or {}).get('account', 'new')}"
        with st.form(form_key):
            name = st.text_input("姓名", value=str((selected_user or {}).get("name", "")))
            account = st.text_input(
                "帳號／工號",
                value=str((selected_user or {}).get("account", "")),
                disabled=selected_user is not None,
                help="既有人員的帳號作為唯一識別，修改時不可變更。",
            )
            department = st.selectbox(
                "所屬課別",
                DEPARTMENTS,
                index=DEPARTMENTS.index(initial_department),
            )
            role = st.selectbox(
                "角色／權限",
                list(ROLE_LEVELS.keys()),
                index=list(ROLE_LEVELS.keys()).index(initial_role),
            )
            active = st.checkbox(
                "啟用帳號",
                value=str((selected_user or {}).get("active", "TRUE")).upper() == "TRUE",
            )
            direct_password = st.text_input(
                "設定新密碼",
                type="password",
                help="新增時空白使用預設密碼 0000；修改時空白代表保留原密碼。",
            )
            submitted = st.form_submit_button(
                "新增人員" if edit_mode == "新增人員" else "儲存修改",
                width="stretch",
            )
            if submitted:
                if not name.strip() or not account.strip():
                    st.error("姓名與帳號／工號為必填。")
                elif edit_mode == "新增人員" and UserService.get_by_account(account):
                    st.error("此帳號／工號已存在，請改用「修改既有人員」。")
                else:
                    result = UserService.upsert_user(
                        name=name,
                        account=account,
                        role=role,
                        role_level=ROLE_LEVELS[role],
                        active=active,
                        direct_password=direct_password,
                        department=department,
                    )
                    st.success("人員已新增。" if result == "created" else "人員資料已修改。")
                    st.rerun()

    with st.expander("🗑️ 刪除人員", expanded=False):
        if department_users:
            delete_options = {
                f"{user.get('name', '')}（{user.get('account', '')}）": user.get("account", "")
                for user in department_users
            }
            delete_label = st.selectbox("選擇要刪除的人員", list(delete_options.keys()))
            confirm_delete = st.checkbox("我確認要永久刪除此人員", key="personnel_confirm_delete")
            if st.button("永久刪除", type="primary", disabled=not confirm_delete):
                ok, message = UserService.delete_user(delete_options[delete_label])
                (st.success if ok else st.error)(message)
                if ok:
                    st.rerun()
        else:
            st.info("此課別沒有可刪除的人員。")
