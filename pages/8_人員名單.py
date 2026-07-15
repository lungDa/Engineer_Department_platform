import pandas as pd
import streamlit as st

from config.departments import DEPARTMENTS
from config.roles import ROLE_LEVELS
from utils import AppInitializer, UserService


st.set_page_config(page_title="人員名單｜課別分類", layout="wide")
AppInitializer.setup(load_tasks=False, load_meetings=False, load_approvals=False)

st.header("👥 人員名單｜課別分類")
st.caption("人員資料依課別獨立整理；停用帳號不會出現在一般人員名單。")

management_unlocked = st.session_state.get("personnel_management_unlocked", False)
if management_unlocked:
    login_col, logout_col = st.columns([5, 1])
    with login_col:
        st.success(
            f"🔓 人員管理已啟用：{st.session_state.get('management_user', '')}｜"
            f"權限 {st.session_state.get('management_role_level', 0)}"
        )
    with logout_col:
        if st.button("結束人員管理", width="stretch"):
            st.session_state["personnel_management_unlocked"] = False
            if not st.session_state.get("developer_diagnostics_unlocked", False):
                st.session_state.pop("management_user", None)
                st.session_state.pop("management_role_level", None)
            st.rerun()
else:
    st.info("🔒 目前為唯讀模式。只有按下人員管理功能時，才會要求權限 6～9 的帳號與密碼。")
    if st.button("🔐 開啟人員管理", type="primary"):
        st.session_state["show_personnel_permission_login"] = True

    if st.session_state.get("show_personnel_permission_login", False):
        with st.form("personnel_permission_login"):
            permission_account = st.text_input("帳號／工號")
            permission_password = st.text_input("密碼", type="password")
            submitted = st.form_submit_button("驗證人員管理權限", width="stretch")
            if submitted:
                ok, message, user = UserService.verify_management_credentials(
                    permission_account, permission_password, minimum_level=6
                )
                if ok:
                    st.session_state["personnel_management_unlocked"] = True
                    st.session_state["management_user"] = user.get("name", permission_account)
                    st.session_state["management_role_level"] = UserService.effective_role_level(user)
                    st.session_state["show_personnel_permission_login"] = False
                    st.success("權限驗證成功。")
                    st.rerun()
                else:
                    st.error(message)

all_users = [
    user for user in UserService.get_active_users()
    if str(user.get("department") or "") != "系統獨立"
]
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

# 所有部門共用同一組欄位、順序、寬度與表格高度，避免各表格隨內容偏移。
PERSONNEL_COLUMNS = ["課別", "姓名", "帳號／工號", "本課職務", "最高權限"]
PERSONNEL_COLUMN_CONFIG = {
    "課別": st.column_config.TextColumn("課別", width="medium"),
    "姓名": st.column_config.TextColumn("姓名", width="small"),
    "帳號／工號": st.column_config.TextColumn("帳號／工號", width="medium"),
    "本課職務": st.column_config.TextColumn("本課職務", width="large"),
    "最高權限": st.column_config.NumberColumn("最高權限", width="small", format="%d"),
}
# 固定顯示表頭＋3 筆人員資料；第 4 筆起由表格內垂直滾輪查看。
PERSONNEL_TABLE_HEIGHT = 143

for department in DEPARTMENTS:
    users = UserService.get_users_by_department(department)
    if keyword.strip():
        key = keyword.strip().lower()
        users = [
            user for user in users
            if key in str(user.get("name", "")).lower()
            or key in str(user.get("account", "")).lower()
            or key in str(user.get("role", "")).lower()
            or any(key in str(item.get("role", "")).lower() for item in UserService.get_assignments(user))
        ]

    with st.expander(f"🏢 {department}　｜　{len(users)} 人", expanded=department == st.session_state.current_department):
        rows = [
            {
                "課別": department,
                "姓名": user.get("name", ""),
                "帳號／工號": user.get("account", ""),
                "本課職務": "、".join(UserService.roles_in_department(user, department)),
                "最高權限": UserService.effective_role_level(user),
            }
            for user in sorted(users, key=lambda item: str(item.get("name", "")))
        ]
        personnel_df = pd.DataFrame(rows, columns=PERSONNEL_COLUMNS)
        st.dataframe(
            personnel_df,
            width="stretch",
            height=PERSONNEL_TABLE_HEIGHT,
            hide_index=True,
            column_order=PERSONNEL_COLUMNS,
            column_config=PERSONNEL_COLUMN_CONFIG,
        )
        if not users:
            st.caption("此課別目前沒有符合條件的啟用人員。")


if management_unlocked:
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
    operator_level = int(st.session_state.get("management_role_level", 0) or 0)
    manageable_users = [
        user for user in department_users
        if UserService.effective_role_level(user) <= operator_level
    ]

    edit_mode = st.radio("管理動作", ["新增人員", "修改既有人員"], horizontal=True)
    selected_user = None
    if edit_mode == "修改既有人員":
        if manageable_users:
            user_options = {
                f"{user.get('name', '')}（{user.get('account', '')}）": user
                for user in manageable_users
            }
            selected_label = st.selectbox("選擇要修改的人員", list(user_options.keys()))
            selected_user = user_options[selected_label]
        else:
            st.warning("此課別目前沒有人員可修改，請改用新增人員。")

    can_edit = edit_mode == "新增人員" or selected_user is not None
    if can_edit:
        initial_role = str((selected_user or {}).get("role") or "助理工程師")
        if initial_role not in ROLE_LEVELS:
            initial_role = "助理工程師"
        initial_department = str((selected_user or {}).get("department") or manage_department)
        if initial_department not in DEPARTMENTS:
            initial_department = manage_department
        current_assignments = UserService.get_assignments(selected_user)[1:] if selected_user else []

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
            allowed_roles = [name for name, level in ROLE_LEVELS.items() if level <= operator_level]
            role = st.selectbox(
                "角色／權限",
                allowed_roles,
                index=allowed_roles.index(initial_role) if initial_role in allowed_roles else len(allowed_roles) - 1,
            )
            assignment_options = [
                f"{department_name}｜{role_name}"
                for department_name in DEPARTMENTS
                for role_name, level in ROLE_LEVELS.items()
                if level <= operator_level
            ]
            assignment_defaults = [
                f"{item.get('department')}｜{item.get('role')}"
                for item in current_assignments
                if f"{item.get('department')}｜{item.get('role')}" in assignment_options
            ]
            concurrent_positions = st.multiselect(
                "兼任職務（可複選）",
                assignment_options,
                default=assignment_defaults,
                help="同一人可兼任不同課別或同課別的其他職務。權限取所有職務中的最高值。",
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
                    assignments = []
                    for position in concurrent_positions:
                        assignment_department, assignment_role = position.split("｜", 1)
                        if assignment_department == department and assignment_role == role:
                            continue
                        assignments.append({
                            "department": assignment_department,
                            "role": assignment_role,
                            "role_level": ROLE_LEVELS[assignment_role],
                        })
                    result = UserService.upsert_user(
                        name=name,
                        account=account,
                        role=role,
                        role_level=ROLE_LEVELS[role],
                        active=active,
                        direct_password=direct_password,
                        department=department,
                        assignments=assignments,
                    )
                    st.success("人員已新增。" if result == "created" else "人員資料已修改。")
                    st.rerun()

    with st.expander("🗑️ 刪除人員", expanded=False):
        if manageable_users:
            delete_options = {
                f"{user.get('name', '')}（{user.get('account', '')}）": user.get("account", "")
                for user in manageable_users
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
