import streamlit as st
from datetime import datetime


# 在 utils.py 最上方加入這段
class AppInitializer:
    @staticmethod
    def setup():
        from datetime import date, timedelta
        if 'tasks' not in st.session_state:
            st.session_state.tasks = [
                {"id": 1, "title": "資料庫設計", "category": "進行中", "due": date.today()+timedelta(days=2), "assignees": ["王大明"], "status": "Active", "progress": 80, "hours_spent": 4.5, "importance": "高", "urgency": "高", "history": []},
                {"id": 2, "title": "API 開發", "category": "待辦事項", "due": date.today()+timedelta(days=5), "assignees": ["陳小華"], "status": "Active", "progress": 0, "hours_spent": 0.0, "importance": "高", "urgency": "低", "history": []}
            ]
            st.session_state.partners = ["王大明", "陳小華", "林志玲", "闕老師"]
            st.session_state.current_user = "闕老師"
            st.session_state.roles = {"闕老師": 2, "王大明": 1, "陳小華": 0, "林志玲": 0}
            st.session_state.categories = ["待辦事項", "進行中", "已完成"]
            st.session_state.meetings = []
            st.session_state.approvals = []
            st.session_state.tags_list = ["設計", "開發", "測試"]
            st.session_state.cal_year = date.today().year
            st.session_state.cal_month = date.today().month
            st.session_state.selected_date = date.today()

class ViewComponents:
    """可重用的 UI 元件"""
    @staticmethod
    def render_filters():
        with st.expander("🔍 進階多維度篩選器", expanded=False):
            c1, c2 = st.columns(2)
            with c1: f_a = st.multiselect("篩選指派對象", st.session_state.partners)
            with c2: f_t = st.multiselect("篩選標籤", st.session_state.tags_list)
            return f_a, f_t

class StreamFlowEngine:

    @staticmethod
    def add_log(task, message):
        from datetime import datetime
        if 'history' not in task: task['history'] = []
        task['history'].append(f"[{datetime.now().strftime('%m-%d %H:%M')}] {st.session_state.current_user} {message}")

class TaskService:
    """處理所有與任務相關的邏輯"""
    @staticmethod
    def get_filtered_tasks(f_assignees, f_tags, tasks=None):
        if tasks is None: tasks = st.session_state.tasks
        filtered = []
        for t in tasks:
            if t['status'] != 'Active': continue
            match_assignee = (not f_assignees) or any(a in f_assignees for a in t.get('assignees', []))
            match_tag = (not f_tags) or (t.get('tags') in f_tags)
            if match_assignee and match_tag: filtered.append(t)
        return filtered

    @staticmethod
    def is_task_locked(task):
        locked_by = [t['title'] for t in st.session_state.tasks if t['id'] in task.get('depends_on', []) and t['category'] != '已完成' and t['status'] == 'Active']
        return len(locked_by) > 0, locked_by

    @staticmethod
    def calculate_team_capacity():
        import pandas as pd
        active_tasks = [t for t in st.session_state.tasks if t['status'] == 'Active']
        load_data = []
        for p in st.session_state.partners:
            active_count = len([t for t in active_tasks if p in t.get('assignees', []) and t['category'] == '進行中'])
            ready_count = len([t for t in active_tasks if p in t.get('assignees', []) and t['category'] == '待辦事項'])
            weight = (active_count * 1.0) + (ready_count * 0.3)
            load_data.append({"夥伴": p, "進行中(權重1.0)": active_count, "待辦(權重0.3)": ready_count, "總負載權重": round(weight, 1)})
        return pd.DataFrame(load_data)

class MeetingService:
    @staticmethod
    def get_visible_meetings(target_date=None):
        user = st.session_state.current_user
        role_level = st.session_state.roles.get(user, 0)
        meetings = st.session_state.meetings
        visible = [m for m in meetings if (user in m['attendees'] or role_level > st.session_state.roles.get(m['owner'], 0) or user == m['owner'])]
        if target_date:
            visible = [m for m in visible if m['time'] == target_date]
        return visible

class ApprovalService:
    @staticmethod
    def process_action(approval, action, reason, transfer_to=None):
        now_str = datetime.now().strftime('%m-%d %H:%M')
        if action == "同意":
            approval['status'] = "已同意"
            approval['history'].append(f"[{now_str}] {st.session_state.current_user} 同意。意見: {reason}")
        elif action == "駁回":
            approval['status'] = "已駁回"
            approval['history'].append(f"[{now_str}] {st.session_state.current_user} 駁回。意見: {reason}")
        elif action == "轉交":
            approval['current_signer'] = transfer_to
            approval['history'].append(f"[{now_str}] {st.session_state.current_user} 轉交給 {transfer_to}。意見: {reason}")