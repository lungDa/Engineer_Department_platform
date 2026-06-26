# StreamFlow 專業任務管理系統

這是一套以 Streamlit 製作的專案管理平台，包含任務看板、艾森豪矩陣、專案行事曆、甘特圖、效率分析、會議系統與簽核中心。

## 功能

- 任務看板：分類欄位、進度、工時、備註、活動紀錄
- 艾森豪矩陣：依重要度與緊急度分類任務
- 專案行事曆：月曆式查看任務與會議
- 甘特圖：Plotly 視覺化專案排程
- 效率分析：任務狀態、逾期項目、團隊負載
- 會議系統：建立會議、紀要與權限檢視
- 簽核中心：發起、同意、駁回、轉交簽核

## 本機執行

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

macOS / Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## 部署到 Streamlit Community Cloud

1. 將此資料夾內容推上 GitHub。
2. 到 Streamlit Community Cloud 建立 App。
3. Repository 選擇你的 GitHub 專案。
4. Main file path 填入：

```text
app.py
```

5. Deploy。

## 專案結構

```text
StreamFlow_GitHub/
├── app.py
├── utils.py
├── requirements.txt
├── README.md
├── .gitignore
├── .streamlit/
│   ├── config.toml
│   └── secrets.example.toml
└── pages/
    ├── 1_任務看板.py
    ├── 2_艾森豪矩陣.py
    ├── 3_專案行事曆.py
    ├── 4_專案甘特圖.py
    ├── 5_效率統計分析.py
    ├── 6_會議系統.py
    └── 7_簽核中心.py
```

## 注意事項

- `.streamlit/secrets.toml` 不可上傳 GitHub。
- 目前版本使用 `st.session_state` 暫存資料，重新整理或重啟後會回到預設資料。
- 若要正式多人使用，建議下一版串接 Google Sheet、PostgreSQL 或 Supabase。
