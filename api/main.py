from fastapi import FastAPI

from config.settings import get_settings
from services.config_service import config_service
from services.line_service import line_service
from services.ai_service import ai_service
from shared.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

app = FastAPI(
    title=f"{settings.app_name} API",
    version=settings.app_version,
    description="V5 Enterprise API service for LINE Smart Assistant, automation, and platform integration.",
)


@app.on_event("startup")
async def startup_event():
    logger.info("API service started: %s", settings.app_version)


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": f"{settings.app_name} API",
        "version": settings.app_version,
        "environment": settings.environment,
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "api",
        "version": settings.app_version,
    }


@app.get("/api/info")
def api_info():
    return config_service.get_public_info()


@app.get("/api/service-status")
def service_status():
    return {
        "status": "ok",
        "version": settings.app_version,
        "line": line_service.get_status(),
        "ai": {
            "configured": ai_service.is_configured(),
            "features": {
                "chat": False,
                "task_analysis": False,
                "equipment_query": False,
            },
        },
    }
