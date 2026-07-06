import json

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
    status,
)

from api.dependencies.services import (
    get_line_command_service,
    get_line_service,
)

router = APIRouter(
    prefix="/api/line",
    tags=["LINE"],
)


@router.get("/status")
def line_status(
    line_service=Depends(get_line_service),
):
    return {
        "ok": True,
        "data": line_service.get_status(),
    }


@router.post("/webhook")
async def line_webhook(
    request: Request,
    x_line_signature: str | None = Header(
        default=None,
        alias="X-Line-Signature",
    ),
    line_service=Depends(get_line_service),
    line_command_service=Depends(get_line_command_service),
):
    """
    LINE Official Account Webhook
    """

    body = await request.body()

    # =====================================================
    # Signature 驗證
    # =====================================================
    if not line_service.validate_signature(
        body,
        x_line_signature,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid LINE signature.",
        )

    # =====================================================
    # JSON 解析
    # =====================================================
    try:
        payload = json.loads(body.decode("utf-8"))

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload.",
        )

    # =====================================================
    # 取得文字事件
    # =====================================================
    text_events = line_service.extract_text_events(
        payload
    )

    replies = []

    # =====================================================
    # 回覆訊息
    # =====================================================
    for event in text_events:

        reply_text = line_command_service.handle_text(
            text=event.get("text", ""),
            user_id=event.get("user_id"),
        )

        result = line_service.reply_text(
            reply_token=event.get("reply_token"),
            text=reply_text,
        )

        replies.append(
            {
                "user_id": event.get("user_id"),
                "text": event.get("text"),
                "reply_ok": result.get("ok"),
            }
        )

    return {
        "ok": True,
        "message": "Webhook processed.",
        "event_count": len(payload.get("events", [])),
        "text_event_count": len(text_events),
        "replies": replies,
    }


@router.post("/webhook-test")
async def line_webhook_test(
    request: Request,
    line_command_service=Depends(
        get_line_command_service
    ),
):
    """
    Local test endpoint

    Example

    {
        "text": "我的任務",
        "user_id": "test-user"
    }
    """

    payload = await request.json()

    text = payload.get("text", "")
    user_id = payload.get("user_id")

    reply = line_command_service.handle_text(
        text=text,
        user_id=user_id,
    )

    return {
        "ok": True,
        "reply": reply,
    }
