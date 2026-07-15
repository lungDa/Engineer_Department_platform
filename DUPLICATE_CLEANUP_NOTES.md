# 重複程式整理紀錄

本版以資料夾內模組為唯一程式來源。

## 保留
- `services/core.py`
- `pages/1_任務看板.py`
- `pages/2_艾森豪矩陣.py`
- `pages/6_會議系統.py`

## 移除的根目錄重複檔案
- `core.py`
- `1_任務看板.py`
- `2_艾森豪矩陣.py`
- `6_會議系統.py`
- 根目錄 `__pycache__/`

所有既有 import 已確認使用 `services.core`，不需改寫。
Streamlit 多頁功能會從 `pages/` 資料夾載入頁面。
