from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.dependencies.services import get_mail_service, get_teams_service

router = APIRouter(prefix="/api/notifications", tags=["Microsoft 365 Notifications"])


class TeamsNotificationRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=5000)
    level: str = Field(default="info", max_length=20)
    facts: dict[str, Any] = Field(default_factory=dict)
    source_url: str = Field(default="", max_length=2000)


class OutlookMailRequest(BaseModel):
    to: list[str] = Field(min_length=1)
    cc: list[str] = Field(default_factory=list)
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(default="", max_length=50000)
    is_html: bool = False


@router.get("/status")
def notification_status(
    teams_service=Depends(get_teams_service),
    mail_service=Depends(get_mail_service),
):
    return {
        "status": "ok",
        "teams": teams_service.get_status(),
        "outlook": mail_service.get_status(),
    }


@router.post("/teams/test")
def send_teams_test(
    request: TeamsNotificationRequest,
    teams_service=Depends(get_teams_service),
):
    return teams_service.send(**request.model_dump())


@router.post("/outlook/test")
def send_outlook_test(
    request: OutlookMailRequest,
    mail_service=Depends(get_mail_service),
):
    return mail_service.send(**request.model_dump())
