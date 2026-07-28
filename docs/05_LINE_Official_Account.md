# 05 LINE Official Account

## Setup

1. Create LINE Official Account
2. Create Messaging API Channel
3. Issue Channel Access Token
4. Configure Render Environment Variables
5. Set Webhook URL

```
https://<api-domain>/api/line/webhook
```

Enable:

- Use Webhook
- Messaging API

Disable:

- Auto Reply (recommended during testing)

## Test

```
POST /api/line/webhook-test
```

Example

```json
{
  "text":"說明",
  "user_id":"demo"
}
```

## 從 LINE 建立任務

使用者必須先在官方帳號聊天室完成平台帳號綁定：

```text
綁定 工號 密碼
```

綁定完成後，輸入下列指令開始建立任務：

```text
#任務
```

系統會以問答方式依序詢問「任務內容、指派人員、截止日期」，
過程中可輸入「取消」結束建立。多人指派可使用頓號或逗號分隔。
平台會直接以任務內容作為任務名稱，不需要另外輸入標題。

系統會先驗證 LINE 綁定、人員姓名及日期格式；驗證通過後才寫入
Google Sheet 的 `Tasks`，接著個別通知指派人員的 Teams、Outlook
與 LINE。任一通知失敗不會回滾已建立的任務，LINE 回覆會明確列出
失敗管道。
