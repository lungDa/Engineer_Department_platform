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

from datetime import datetime

def render_task(task):

    assignees = task.get("assignees", [])

    if isinstance(assignees, str):
        assignees = [
            x.strip()
            for x in assignees.replace(";", ",").split(",")
            if x.strip()
        ]

    # ------------------------
    # 指派人員 Badge
    # ------------------------

    badges = ""

    colors = [
        "#2563EB",
        "#16A34A",
        "#CA8A04",
        "#9333EA",
        "#DC2626",
        "#0891B2"
    ]

    for i, person in enumerate(assignees):

        color = colors[i % len(colors)]

        badges += f"""
        <span style="
        display:inline-block;
        background:{color};
        color:white;
        padding:4px 10px;
        border-radius:20px;
        margin-right:4px;
        margin-bottom:5px;
        font-size:12px;
        ">
        👤 {person}
        </span>
        """

    # ------------------------
    # Priority
    # ------------------------

    imp = task.get("importance", "低")

    if imp == "高":
        priority = """
        <span style="
        color:white;
        background:#DC2626;
        padding:4px 10px;
        border-radius:15px;
        ">
        🔥 HIGH
        </span>
        """
    else:
        priority = """
        <span style="
        color:white;
        background:#16A34A;
        padding:4px 10px;
        border-radius:15px;
        ">
        LOW
        </span>
        """

    # ------------------------
    # Progress
    # ------------------------

    progress = int(task.get("progress", 0))

    progress_color = "#16A34A"

    if progress < 40:
        progress_color = "#DC2626"

    elif progress < 80:
        progress_color = "#F59E0B"

    # ------------------------
    # 剩餘天數
    # ------------------------

    due = task.get("due", "")

    remain = ""

    try:

        if isinstance(due, str):

            d = datetime.strptime(due, "%Y-%m-%d").date()

        else:

            d = due

        days = (d - datetime.today().date()).days

        if days < 0:

            remain = f"""
            <span style="color:#DC2626;font-weight:bold;">
            🔴 已逾期 {abs(days)} 天
            </span>
            """

        elif days == 0:

            remain = """
            <span style="color:#F59E0B;font-weight:bold;">
            ⚠ 今天到期
            </span>
            """

        else:

            remain = f"""
            <span style="color:#16A34A;">
            ⏳ 剩餘 {days} 天
            </span>
            """

    except:

        remain = ""

    # ------------------------
    # Card
    # ------------------------

    st.markdown(f"""

<div style="
background:white;
border-radius:14px;
padding:16px;
margin-bottom:12px;
box-shadow:0 3px 12px rgba(0,0,0,.12);
border-left:6px solid {progress_color};
">

<div style="
font-size:18px;
font-weight:bold;
">

📌 {task['title']}

</div>

<br>

{badges}

<br>

{priority}

<br><br>

📅 {task.get("due","")}

<br>

{remain}

<br><br>

<div style="
background:#EEE;
height:10px;
border-radius:10px;
">

<div style="
height:10px;
width:{progress}%;
background:{progress_color};
border-radius:10px;
">
</div>

</div>

<div style="
margin-top:5px;
font-size:13px;
">

完成度 {progress}%

</div>

</div>

""", unsafe_allow_html=True)

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

st.markdown("""
<style>

.cross-divider{

height:5px;

background:#444;

border-radius:5px;

margin-top:30px;

margin-bottom:30px;

}

</style>

<div class="cross-divider"></div>

""", unsafe_allow_html=True)
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
