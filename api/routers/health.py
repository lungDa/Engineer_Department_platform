from fastapi import APIRouter

from config.settings import get_settings

router = APIRouter(tags=["Health"])


@router.get("/")
def root():
    settings = get_settings()
    return {
        "status": "ok",
        "service": f"{settings.app_name} API",
        "version": settings.app_version,
        "environment": settings.environment,
    }


@router.get("/health")
def health():
    settings = get_settings()
    return {
        "status": "healthy",
        "service": "api",
        "version": settings.app_version,
    }


@router.get("/ready")
def ready():
    settings = get_settings()
    return {
        "ready": True,
        "version": settings.app_version,
    }
