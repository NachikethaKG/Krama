from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import Settings, get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


@router.get("/health")
def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(status="ok", version=settings.app_version)
