from fastapi import APIRouter, Depends, Request

from api.dependencies.services import get_line_service

router = APIRouter(prefix="/api/line", tags=["LINE"])


@router.get("/status")
def line_status(line_service=Depends(get_line_service)):
    return {
        "ok": True,
        "data": line_service.get_status(),
    }


@router.post("/webhook")
async def line_webhook(request: Request, line_service=Depends(get_line_service)):
    # V5.0.3 only prepares the endpoint.
    # Actual LINE signature validation and reply logic will be implemented in V5.1.
    body = await request.body()
    return {
        "ok": True,
        "message": "LINE webhook endpoint is ready. Handler will be implemented in V5.1.",
        "configured": line_service.is_configured(),
        "received_bytes": len(body),
    }
