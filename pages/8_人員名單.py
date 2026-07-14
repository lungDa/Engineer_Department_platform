import pandas as pd
import streamlit as st

from config.departments import DEPARTMENTS
from utils import AppInitializer, UserService


st.set_page_config(page_title="人員名單｜課別分類", layout="wide")
AppInitializer.setup(load_tasks=False, load_meetings=False, load_approvals=False)

st.header("👥 人員名單｜課別分類")
st.caption("人員資料依課別獨立整理；停用帳號不會出現在一般人員名單。")

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
