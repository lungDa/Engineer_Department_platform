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

系統會以問答方式依序詢問任務內容、指派人員與截止日期。

已綁定的使用者可輸入 `修改密碼`，接著直接輸入一次新密碼，
系統會立即更新目前 LINE 綁定工號的密碼。

輸入 `#請假` 可用問答方式提出請假。系統會依序詢問假別、
開始／結束日期、開始／結束時間、請假時數、請假說明與被通知者。
建立成功後會寫入 `Approvals`、簽核中心與專案行事曆，並通知被通知者。

系統會以問答方式依序詢問「任務內容、指派人員、截止日期」，
過程中可輸入「取消」結束建立。多人指派可使用頓號或逗號分隔。
平台會直接以任務內容作為任務名稱，不需要另外輸入標題。

系統會先驗證 LINE 綁定、人員姓名及日期格式；驗證通過後才寫入
Google Sheet 的 `Tasks`，接著個別通知指派人員的 Teams、Outlook
與 LINE。任一通知失敗不會回滾已建立的任務，LINE 回覆會明確列出
失敗管道。
