# V5.5.3 Microsoft 365 Migration Baseline 重複程式整理紀錄

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
- `task_board.py`（完整功能已移入 `pages/1_任務看板.py`）
- 根目錄 `__pycache__/`

所有既有 import 已確認使用 `services.core`，不需改寫。
Streamlit 多頁功能會從 `pages/` 資料夾載入頁面。
本基準修正版已再次確認根目錄 `task_board.py` 未被引用，並完成實際移除。

## 效能調整

- Google Sheet 首次載入改用批次讀取，本頁不需要的資料不載入。
- 使用者、分類與標籤採長效快取；任務、公告、會議與簽核採 5 秒快取。
- 新增、修改或刪除後會立即清除對應快取，資料仍會即時更新。
- 清除各頁重複及未使用的匯入，降低切頁初始化成本。

一秒目標適用於服務已啟動且 Google Sheet 完成首次連線後的切頁與重跑；
Render／Streamlit 冷啟動及 Google API 首次授權屬外部延遲，無法由頁面程式保證在一秒內完成。
