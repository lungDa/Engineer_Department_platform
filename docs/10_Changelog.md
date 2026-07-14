# 10 Changelog

## V5.5.2 Split Announcement Permissions
- 公告發布開放給所有權限 0～9 的啟用人員
- 公告管理維持權限 6～9
- 發布與管理改用兩套獨立權限檢查

## V5.5.1 Announcement Permission Update
- 權限 6～9 可發布與管理公告
- 公告操作時才驗證帳號密碼，不要求首頁登入
- 系統診斷及其餘開發者工具仍限權限 9

## V5.5.0 Concurrent Positions
- 人員支援一個主要職務與多個兼任職務
- 兼任職務可跨課別，也可在同一課別兼任其他角色
- 人員會出現在所有任職課別的人員名單與指派選單
- 有效權限取主要與兼任職務中的最高值
- Users 新增 assignments JSON 欄位

## V5.4.0 Role Permission Matrix
- 角色固定對應權限 9～0：開發者、經理、副理、管理師、專案經理、課長、組長、資深工程師、工程師、助理工程師
- 權限 6 以上可管理人員名單
- 所有人均可新增任務及修改任務進度
- 公告與系統診斷等其他管理功能僅限開發者（權限 9）
- 管理者不可指派高於自身的角色權限
- 首頁僅保留開發者驗證；其他角色在點選人員管理時才驗證帳號與密碼

## V5.3.3 Personnel Permission Gate
- 人員名單預設為唯讀
- 僅在首頁完成開發者密碼驗證後開放人員新增、修改、停用與刪除
- 修改人員時可調整姓名、課別、角色、權限、啟用狀態與密碼
- 登出開發者模式後立即恢復唯讀

## V5.3.2 Department Personnel Directory
- 新增 pages/8_人員名單.py
- 人員名單依 11 個課別分組顯示
- 支援姓名、帳號與角色搜尋
- 開發者面板新增課別欄位及全課別人數總覽

## V5.3.1 Import Hotfix
- 將 DEPARTMENTS 移至獨立 config/departments.py
- 修正 Streamlit Cloud 部署時 utils 相容層版本不同步造成的 ImportError

## V5.3.0 Department Edition
- 11 課別全平台切換與資料隔離
- Users、Tasks、Announcements、Meetings、Approvals 新增 department 欄位
- 各課別人員名單獨立用於任務、會議與簽核選單
- 開發者可新增、刪除、停用人員並調整角色權限
- API 支援 department 查詢參數

## V5.1.1 Enterprise Diagnostics Center
- Enterprise Diagnostics
- LINE Official Account Integration
- Render API Health Check
- Repository Layer Improvements

## V5.1.0
- LINE Smart Assistant
- Webhook
- Command Router

## V5.0.4
- Repository Pattern
- Cache Layer

## V5.0.3
- FastAPI API Layer

## V5.0.2
- Service Layer Refactor

## V5.0.1
- Foundation Architecture

## V4.x
- Streamlit Enterprise Dashboard
- Google Sheet Task Management
