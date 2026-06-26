import streamlit as st
import plotly.express as px
import pandas as pd
from datetime import timedelta
from utils import TaskService, StreamFlowEngine as engine

st.header("📊 專案甘特圖")
from utils import AppInitializer, StreamFlowEngine, ViewComponents, TaskService # 根據該頁面需求 import
AppInitializer.setup()

data = [{"Task": t['title'], "Start": t['due'], "Finish": t['due'] + timedelta(days=1), "Resource": t['category']} 
                for t in st.session_state.tasks if t['status'] == 'Active']
if data:
	fig = px.timeline(pd.DataFrame(data), x_start="Start", x_end="Finish", y="Task", color="Resource")
	fig.update_yaxes(autorange="reversed")
	st.plotly_chart(fig, use_container_width=True)
else:
	st.info("目前沒有任務資料可供生成甘特圖。")
