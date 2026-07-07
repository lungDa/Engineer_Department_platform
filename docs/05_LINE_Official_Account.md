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
