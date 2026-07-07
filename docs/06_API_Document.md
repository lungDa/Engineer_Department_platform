# 06 API Documentation

## Base URL

```
https://<render-api>
```

## Health

### GET /health

Checks service health.

Response

```json
{
  "status":"healthy"
}
```

## Tasks

GET /api/tasks

GET /api/tasks/active

GET /api/tasks/completed

GET /api/tasks/{task_id}

## Users

GET /api/users

GET /api/users/active

## Announcements

GET /api/announcements

GET /api/announcements/active

## LINE

GET /api/line/status

POST /api/line/webhook

POST /api/line/webhook-test

## Error Codes

|Code|Meaning|
|---|---|
|200|Success|
|400|Bad Request|
|403|Invalid LINE Signature|
|404|Not Found|
|500|Internal Server Error|
