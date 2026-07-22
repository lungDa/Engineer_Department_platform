from fastapi import APIRouter, Depends

from api.dependencies.services import (
    get_ai_service,
    get_config_service,
    get_line_service,
    get_mail_service,
    get_teams_service,
)

router = APIRouter(prefix="/api", tags=["System"])


@router.get("/info")
def api_info(config_service=Depends(get_config_service)):
    return config_service.get_public_info()


@router.get("/service-status")
def service_status(
    line_service=Depends(get_line_service),
    teams_service=Depends(get_teams_service),
    mail_service=Depends(get_mail_service),
    ai_service=Depends(get_ai_service),
):
    return {
        "status": "ok",
        "line": line_service.get_status(),
        "teams": teams_service.get_status(),
        "outlook": mail_service.get_status(),
        "ai": {
            "configured": ai_service.is_configured(),
            "features": {
                "chat": False,
                "task_analysis": False,
                "equipment_query": False,
            },
        },
    }
