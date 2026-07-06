import time
from fastapi import Request
from shared.logger import get_logger

logger = get_logger("api.request")


async def request_logging_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed_ms = round((time.time() - start) * 1000, 2)
    logger.info(
        "%s %s -> %s (%sms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    response.headers["X-Process-Time-ms"] = str(elapsed_ms)
    return response
