from typing import Annotated

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.contracts_gen.health_schema import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health")
def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(status="ok", version=settings.app_version)
