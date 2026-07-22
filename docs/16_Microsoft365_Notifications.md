# 16 Microsoft 365 Teams 與 Outlook 通知

本版本透過 Power Automate 的 Webhook 流程，把平台通知送往 Teams 與 Outlook。
流程網址視同密碼，只能存放在 Render 環境變數，不可提交至 GitHub。

## 環境變數

```text
TEAMS_WEBHOOK_URL=
OUTLOOK_WEBHOOK_URL=
M365_WEBHOOK_TOKEN=
```

`M365_WEBHOOK_TOKEN` 是選用的共用驗證值；設定後，平台會以
`X-Platform-Token` HTTP 標頭送出。若 Power Automate 流程無法讀取或驗證
自訂標頭，可保持空白，並以流程網址本身的機密性作為第一階段保護。

## Teams 流程接收格式

```json
{
  "title": "任務通知",
  "message": "有一筆新任務",
  "level": "info",
  "facts": {"負責人": "王小明"},
  "source_url": "https://platform.example.com",
  "system": "Engineer Department Platform",
  "version": "V5.6.0 Microsoft 365 Notifications Foundation"
}
```

Power Automate 建議步驟：

1. 建立可接收 Webhook 的 Teams 工作流程。
2. 解析上方 JSON 欄位。
3. 使用「在聊天或頻道中張貼訊息」動作。
4. 將產生的 URL 設為 Render 的 `TEAMS_WEBHOOK_URL`。

## Outlook 流程接收格式

```json
{
  "to": ["user@example.com"],
  "cc": [],
  "subject": "平台通知",
  "body": "郵件內容",
  "is_html": false,
  "system": "Engineer Department Platform",
  "version": "V5.6.0 Microsoft 365 Notifications Foundation"
}
```

Power Automate 建議步驟：

1. 建立接收 HTTP／Webhook 請求的雲端流程。
2. 將 `to`、`cc` 陣列轉成分號分隔字串。
3. 使用「傳送電子郵件 (V2)」動作。
4. 將產生的 URL 設為 Render 的 `OUTLOOK_WEBHOOK_URL`。

## 測試 API

```text
GET  /api/notifications/status
POST /api/notifications/teams/test
POST /api/notifications/outlook/test
```

本版只建立通知服務與測試入口，尚未自動綁定任務、會議或簽核事件。
