import streamlit as st
import plotly.express as px
import pandas as pd
from utils import StreamFlowEngine as engine
from utils import TaskService, StreamFlowEngine as engine
from datetime import date

st.header("📈 效率統計分析")
from utils import AppInitializer, StreamFlowEngine, ViewComponents, TaskService # 根據該頁面需求 import
AppInitializer.setup()
active = [t for t in st.session_state.tasks if t['status'] == 'Active']

if not active:
    st.info("尚無數據可分析。")
else:
    today = date.today()

    kpi1, kpi2, kpi3 = st.columns(3)

    kpi1.metric("進行中任務總數", len(active))

    kpi2.metric(
        "✅ 已完成任務",
        len([t for t in active if t['category'] == '已完成'])
    )

    overdue = [
        t for t in active
        if t['due'] < today and t['category'] != '已完成'
    ]

    kpi3.metric(
        "🚨 逾期未完成",
        len(overdue),
        delta=f"{len(overdue)} 件延遲",
        delta_color="inverse"
    )

    st.divider()

    st.subheader("🔥 團隊負載熱度儀表板 (Capacity Heatmap)")
    load_df = TaskService.calculate_team_capacity()

    st.dataframe(
        load_df.style.background_gradient(
            subset=['總負載權重'],
            cmap='Reds'
        ),
        use_container_width=True
    )

    if any(load_df['總負載權重'] > 2.0):
        st.warning("⚠️ 警告：有夥伴的總負載權重超過 2.0，建議重新分配任務！")

    st.divider()

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("📊 任務狀態分佈")
        cat_counts = pd.DataFrame(active)['category'].value_counts()

        st.plotly_chart(
            px.pie(
                values=cat_counts.values,
                names=cat_counts.index,
                hole=0.4
            ),
            use_container_width=True
        )

    with c2:
        st.subheader("👥 夥伴任務負載(原始數量)")
        st.plotly_chart(
            px.bar(
                load_df,
                x='夥伴',
                y=['進行中(權重1.0)', '待辦(權重0.3)'],
                barmode='stack'
            ),
            use_container_width=True
        )

    if overdue:
        st.divider()
        st.subheader("⚠️ 逾期任務明細")

        df_o = pd.DataFrame(overdue)[
            ['title', 'category', 'due', 'assignees']
        ]

        df_o['assignees'] = df_o['assignees'].apply(
            lambda x: ", ".join(x) if x else "尚未指派"
        )

        df_o.columns = ['任務名稱', '目前狀態', '原訂截止日', '負責夥伴']

        st.dataframe(df_o, use_container_width=True)