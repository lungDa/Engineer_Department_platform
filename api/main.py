from fastapi import FastAPI
from config.settings import get_settings
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
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "streamlit_base_url": settings.streamlit_base_url,
        "api_base_url": settings.api_base_url,
    }
