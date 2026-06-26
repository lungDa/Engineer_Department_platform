import streamlit as st
from datetime import datetime
from utils import StreamFlowEngine as engine
from utils import AppInitializer, StreamFlowEngine, ViewComponents, TaskService,ApprovalService # 根據該頁面需求 import

AppInitializer.setup()

st.header("✍️ 文件簽核系統 (Workflow)")

with st.expander("📝 發起新簽呈"):
    with st.form("add_app"):
        t = st.selectbox("類型", ["請假單", "請款單", "公假單", "公差單"])
        c = st.text_area("內容說明")
        s = st.selectbox("第一關簽核人", st.session_state.partners)

        if st.form_submit_button("送出簽呈"):
            new_app = {
                "id": len(st.session_state.approvals) + 1,
                "type": t,
                "content": c,
                "sender": st.session_state.current_user,
                "current_signer": s,
                "status": "簽核中",
                "history": []
            }

            engine.add_log(new_app, "發起申請")
            st.session_state.approvals.append(new_app)
            st.success("簽呈已送出！")
            st.rerun()

c1, c2 = st.columns(2)

with c1:
    st.subheader("📥 待我簽核")

    pending = [
        a for a in st.session_state.approvals
        if a['current_signer'] == st.session_state.current_user
        and a['status'] == "簽核中"
    ]

    if not pending:
        st.info("沒有待簽核文件。")

    for a in pending:
        with st.container(border=True):
            st.markdown(f"**[{a['type']}]** 申請人: {a['sender']}")
            st.write(f"內容: {a['content']}")

            act = st.radio(
                "動作",
                ["同意", "駁回", "轉交"],
                key=f"act_{a['id']}"
            )

            trans = (
                st.selectbox(
                    "轉交給",
                    st.session_state.partners,
                    key=f"tr_{a['id']}"
                )
                if act == "轉交"
                else None
            )

            rsn = st.text_input("意見", key=f"rsn_{a['id']}")

            if st.button("確認", key=f"sub_{a['id']}"):
                ApprovalService.process_action(a, act, rsn, trans)
                st.rerun()

with c2:
    st.subheader("📤 我發起的簽呈")

    my_apps = [
        a for a in st.session_state.approvals
        if a['sender'] == st.session_state.current_user
    ]

    if not my_apps:
        st.info("沒有發起的簽呈。")

    for a in my_apps:
        with st.container(border=True):
            color = (
                "🟢" if a['status'] == "已同意"
                else "🔴" if a['status'] == "已駁回"
                else "🟡"
            )

            st.markdown(f"**{color} [{a['type']}]** 狀態: {a['status']}")

            if a['status'] == "簽核中":
                st.write(f"停留在: **{a['current_signer']}**")

            with st.expander("📜 歷史紀錄"):
                for h in a['history']:
                    st.caption(h)