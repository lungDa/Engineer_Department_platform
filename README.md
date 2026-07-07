
# 🚀 Engineer Department Platform

> Enterprise Engineering Management Platform built with **Streamlit + FastAPI + Google Sheets + LINE Official Account**

![Version](https://img.shields.io/badge/version-V5.1.1-blue)
![Python](https://img.shields.io/badge/Python-3.11+-green)
![Streamlit](https://img.shields.io/badge/Streamlit-UI-red)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688)
![Google Sheets](https://img.shields.io/badge/Google%20Sheets-Data-success)
![LINE](https://img.shields.io/badge/LINE-Official%20Account-00B900)

---

## 📌 Project Overview

Engineer Department Platform 是一套企業內部工程管理平台。

目前整合：

- Streamlit Enterprise Dashboard
- FastAPI API Service
- Google Sheet Database
- LINE Official Account
- Repository Pattern
- Enterprise Diagnostics Center

---

# ✨ Current Features

## 任務管理

- 任務看板
- 任務搜尋
- 指派
- 優先級
- 到期提醒
- KPI

## 專案管理

- 艾森豪矩陣
- 甘特圖
- 行事曆

## 協作

- 公告系統
- 會議系統
- 簽核中心

## Platform

- Google Sheet 同步
- FastAPI
- Repository Layer
- Enterprise Diagnostics
- LINE Smart Assistant

---

# 🏗 Architecture

```text
GitHub
    │
Render
 ┌──┴────────────┐
 │               │
Streamlit     FastAPI
 │               │
 └──────┬────────┘
        │
 Service Layer
        │
 Repository Layer
        │
 Google Sheet
        │
 LINE Official Account
```

---

# 📁 Project Structure

```text
app.py
pages/
api/
repositories/
services/
config/
shared/
components/
assets/
utils/
render-api.yaml
render-streamlit.yaml
```

---

# ⚙ Environment Variables

```env
APP_NAME
APP_VERSION
ENVIRONMENT

STREAMLIT_BASE_URL
API_BASE_URL

GOOGLE_SHEET_ID
GOOGLE_SERVICE_ACCOUNT_JSON

LINE_CHANNEL_SECRET
LINE_CHANNEL_ACCESS_TOKEN

OPENAI_API_KEY
```

---

# 📡 API

## Health

GET /health

GET /ready

## Tasks

GET /api/tasks

GET /api/tasks/active

GET /api/tasks/completed

GET /api/tasks/{id}

## Users

GET /api/users

## Announcement

GET /api/announcements

## LINE

GET /api/line/status

POST /api/line/webhook

POST /api/line/webhook-test

---

# 📋 Google Sheet

Worksheets

- Users
- Tasks
- Announcements
- Meetings
- Approvals
- Categories
- Tags

---

# 🤖 LINE Official Account

Current Commands

- 說明
- 狀態
- 我的任務
- 公告

Webhook

/api/line/webhook

---

# 🛠 Enterprise Diagnostics

Developer Mode

- Google Sheet Status
- LINE Status
- Render API
- AI Status
- System Score

---

# 🚀 Deployment

## Streamlit

render-streamlit.yaml

## API

render-api.yaml

---

# 🗺 Roadmap

| Version | Status |
|----------|--------|
| V5.0 Foundation | ✅ |
| V5.0 Service Layer | ✅ |
| V5.0 API Layer | ✅ |
| V5.0 Repository | ✅ |
| V5.1 LINE Smart Assistant | ✅ |
| V5.1 Enterprise Diagnostics | ✅ |
| V5.1.2 LINE User Binding | 🚧 |
| V5.2 AI Assistant | 🚧 |
| V5.3 Gmail / Calendar | 🚧 |
| V5.4 Scheduler | 🚧 |
| V6 Database Migration | 📅 |

---

# 📄 License

Internal Enterprise Project
