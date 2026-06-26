import streamlit as st
from utils import TaskService, StreamFlowEngine as engine
st.header("🔲 艾森豪矩陣 (優先級規劃)")
st.markdown("幫助您釐清任務的輕重緩急。")
from utils import AppInitializer, StreamFlowEngine, ViewComponents, TaskService # 根據該頁面需求 import
AppInitializer.setup()
active = [
    t for t in st.session_state.tasks
    if t['status'] == 'Active' and t['category'] != '已完成'
]

q1 = [t for t in active if t.get('importance') == '高' and t.get('urgency') == '高']
q2 = [t for t in active if t.get('importance') == '高' and t.get('urgency') == '低']
q3 = [t for t in active if t.get('importance') == '低' and t.get('urgency') == '高']
q4 = [t for t in active if t.get('importance') == '低' and t.get('urgency') == '低']

c1, c2 = st.columns(2)
with c1:
    st.error(f"🔥 第一象限：重要且緊急 (立即處理) - {len(q1)}件")
    for t in q1:
        st.info(f"[{t['category']}] {t['title']}")

with c2:
    st.success(f"📅 第二象限：重要但不緊急 (排程規劃) - {len(q2)}件")
    for t in q2:
        st.info(f"[{t['category']}] {t['title']}")

c3, c4 = st.columns(2)
with c3:
    st.warning(f"🤝 第三象限：緊急但不重要 (授權交辦) - {len(q3)}件")
    for t in q3:
        st.info(f"[{t['category']}] {t['title']}")

with c4:
    st.caption(f"🗑️ 第四象限：不重要且不緊急 (減少執行) - {len(q4)}件")
    for t in q4:
        st.info(f"[{t['category']}] {t['title']}")