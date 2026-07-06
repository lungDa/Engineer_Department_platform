from fastapi import FastAPI

from api.middleware.cors import setup_cors
from api.middleware.logging import request_logging_middleware
from api.routers import announcements, health, line, system, tasks, users
from config.settings import get_settings
from shared.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"{settings.app_name} API",
        version=settings.app_version,
        description="V5 Enterprise API service for LINE Smart Assistant, automation, and platform integration.",
    )

    setup_cors(app)
    app.middleware("http")(request_logging_middleware)

    app.include_router(health.router)
    app.include_router(system.router)
    app.include_router(tasks.router)
    app.include_router(users.router)
    app.include_router(announcements.router)
    app.include_router(line.router)

    @app.on_event("startup")
    async def startup_event():
        logger.info("API service started: %s", settings.app_version)

    return app


app = create_app()
