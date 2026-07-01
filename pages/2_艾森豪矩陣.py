import streamlit as st
import pandas as pd
from datetime import datetime,date
from utils import AppInitializer,TaskService

# ============================================================
# 初始化
# ============================================================

st.set_page_config(layout="wide")

AppInitializer.setup()

st.header("🔲 艾森豪矩陣")
st.caption("Enterprise Matrix Dashboard V4.0")

# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>

.block-container{
    padding-top:1rem;
}

.kpi-card{
    background:white;
    border-radius:12px;
    padding:15px;
    text-align:center;
    border:1px solid #ddd;
    box-shadow:0 3px 10px rgba(0,0,0,.08);
}

.kpi-title{
    color:#666;
    font-size:14px;
}

.kpi-value{
    font-size:34px;
    font-weight:bold;
}

.matrix-card{
    border-radius:12px;
    padding:15px;
    min-height:430px;
    border:2px solid #DDD;
}

.q1{
    background:#FFEAEA;
}

.q2{
    background:#ECFFF0;
}

.q3{
    background:#FFF9E7;
}

.q4{
    background:#EAF4FF;
}

.task-card{

    background:white;

    border-radius:10px;

    padding:10px;

    margin-bottom:10px;

    box-shadow:0 2px 6px rgba(0,0,0,.08);

}

.badge{

display:inline-block;

padding:3px 8px;

border-radius:15px;

background:#2563eb;

color:white;

font-size:12px;

margin-right:4px;

margin-bottom:4px;

}

</style>
""",unsafe_allow_html=True)

# ============================================================
# 讀取Task
# ============================================================

tasks=[

t for t in st.session_state.tasks

if t.get("status")=="Active"

and t.get("category")!="已完成"

]

# ============================================================
# 四象限
# ============================================================

q1=[]
q2=[]
q3=[]
q4=[]

for t in tasks:

    imp=t.get("importance","低")

    urg=t.get("urgency","低")

    if imp=="高" and urg=="高":

        q1.append(t)

    elif imp=="高":

        q2.append(t)

    elif urg=="高":

        q3.append(t)

    else:

        q4.append(t)

# ============================================================
# KPI
# ============================================================

k1,k2,k3,k4,k5=st.columns(5)

with k1:

    st.markdown(f"""
<div class="kpi-card">
<div class="kpi-title">全部任務</div>
<div class="kpi-value">{len(tasks)}</div>
</div>
""",unsafe_allow_html=True)

with k2:

    st.markdown(f"""
<div class="kpi-card">
<div class="kpi-title">🔥 第一象限</div>
<div class="kpi-value">{len(q1)}</div>
</div>
""",unsafe_allow_html=True)

with k3:

    st.markdown(f"""
<div class="kpi-card">
<div class="kpi-title">📅 第二象限</div>
<div class="kpi-value">{len(q2)}</div>
</div>
""",unsafe_allow_html=True)

with k4:

    st.markdown(f"""
<div class="kpi-card">
<div class="kpi-title">🤝 第三象限</div>
<div class="kpi-value">{len(q3)}</div>
</div>
""",unsafe_allow_html=True)

with k5:

    st.markdown(f"""
<div class="kpi-card">
<div class="kpi-title">🗑 第四象限</div>
<div class="kpi-value">{len(q4)}</div>
</div>
""",unsafe_allow_html=True)

st.divider()

# ============================================================
# 共用Task Card
# ============================================================

def render_task(task):

    assignees=task.get("assignees",[])

    if isinstance(assignees,str):

        assignees=[

        x.strip()

        for x in assignees.replace(";",",").split(",")

        if x.strip()

        ]

    badges=""

    for p in assignees:

        badges+=f'<span class="badge">{p}</span>'

    progress=task.get("progress",0)

    st.markdown(f"""
<div class="task-card">

<b>📌 {task['title']}</b>

<br><br>

{badges}

<br>

📅 {task.get("due","")}

<br>

完成度 {progress}%

</div>
""",unsafe_allow_html=True)

# ============================================================
# Enterprise Matrix
# ============================================================

st.markdown("""
<style>

.matrix-title{
    font-size:22px;
    font-weight:bold;
    margin-bottom:15px;
}

.matrix-box{

    border-radius:16px;

    padding:18px;

    min-height:560px;

    border:2px solid #DADADA;

    box-shadow:0 3px 10px rgba(0,0,0,.08);

}

.matrix-q1{

    background:#FFECEC;

    border-left:8px solid #DC2626;

}

.matrix-q2{

    background:#EDFFF2;

    border-left:8px solid #16A34A;

}

.matrix-q3{

    background:#FFFBE6;

    border-left:8px solid #EAB308;

}

.matrix-q4{

    background:#EDF6FF;

    border-left:8px solid #2563EB;

}

.matrix-header{

    font-size:20px;

    font-weight:bold;

    margin-bottom:15px;

}

.matrix-sub{

    color:#666;

    font-size:13px;

    margin-bottom:18px;

}

.cross-divider{

    height:3px;

    background:#555;

    margin:18px 0;

}

</style>
""", unsafe_allow_html=True)

# ============================
# 第一列
# ============================

left, right = st.columns(2, gap="large")

with left:

    st.markdown("""
<div class="matrix-box matrix-q1">
<div class="matrix-header">
🔥 第一象限
</div>

<div class="matrix-sub">
重要且緊急（立即處理）
</div>
""", unsafe_allow_html=True)

    if len(q1)==0:

        st.info("目前沒有任務")

    else:

        for task in q1:

            render_task(task)

    st.markdown("</div>", unsafe_allow_html=True)

with right:

    st.markdown("""
<div class="matrix-box matrix-q2">
<div class="matrix-header">
📅 第二象限
</div>

<div class="matrix-sub">
重要但不緊急（規劃排程）
</div>
""", unsafe_allow_html=True)

    if len(q2)==0:

        st.info("目前沒有任務")

    else:

        for task in q2:

            render_task(task)

    st.markdown("</div>", unsafe_allow_html=True)

# ============================
# 中央十字(水平)
# ============================

st.markdown(
    "<div class='cross-divider'></div>",
    unsafe_allow_html=True
)

# ============================
# 第二列
# ============================

left2, right2 = st.columns(2, gap="large")

with left2:

    st.markdown("""
<div class="matrix-box matrix-q3">
<div class="matrix-header">
🤝 第三象限
</div>

<div class="matrix-sub">
緊急但不重要（授權交辦）
</div>
""", unsafe_allow_html=True)

    if len(q3)==0:

        st.info("目前沒有任務")

    else:

        for task in q3:

            render_task(task)

    st.markdown("</div>", unsafe_allow_html=True)

with right2:

    st.markdown("""
<div class="matrix-box matrix-q4">
<div class="matrix-header">
🔵 第四象限
</div>

<div class="matrix-sub">
不重要且不緊急（減少執行）
</div>
""", unsafe_allow_html=True)

    if len(q4)==0:

        st.info("目前沒有任務")

    else:

        for task in q4:

            render_task(task)

    st.markdown("</div>", unsafe_allow_html=True)
