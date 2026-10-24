"""GET /artifacts/{key}: screenshots and recordings, read-only (docs/api-contract.md)."""

import re
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Response

from app.api.auth import CurrentUser
from app.api.errors import ApiException
from app.api.owner import run_owner
from app.api.services import ServicesDep
from app.contracts_gen.common_schema import ErrorResponse
from app.ports import ArtifactNotFoundError, ArtifactStore, InvalidArtifactKeyError
from app.storage import get_artifact_store

router = APIRouter(tags=["artifacts"])
# Every stored file sits under its run (runs/<run_id>/...) and belongs to that run's owner (#94).
_RUN_KEY = re.compile(r"^runs/(?P<run_id>[0-9a-fA-F-]{36})/")

# A stored file is only ever data: the browser must not guess another type or run anything inside it.
_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; sandbox",
    "Cache-Control": "no-cache",  # a retried capture may replace a file under the same key
}
_CONTENT: dict[str, Any] = {"image/png": {}, "image/jpeg": {}, "application/json": {}}


@router.get(
    "/artifacts/{key:path}",
    response_class=Response,
    responses={
        200: {"content": _CONTENT, "description": "The artifact (screenshot PNG/JPEG or JSON)"},
        404: {"model": ErrorResponse, "description": "No artifact with this key"},
    },
)
async def get_artifact(
    key: Annotated[str, Path(description="Relative artifact path, e.g. runs/<run_id>/steps/3-after.png")],
    store: Annotated[ArtifactStore, Depends(get_artifact_store)],
    user: CurrentUser,
    services: ServicesDep,
) -> Response:
    if not await _owns(key, user.id, services):
        raise ApiException(404, "not_found", "Artifact not found")
    try:
        artifact = await store.get(key)
    except (ArtifactNotFoundError, InvalidArtifactKeyError):
        # An unsafe key gets the same answer as a missing one: nothing to learn from probing.
        raise ApiException(404, "not_found", "Artifact not found") from None
    return Response(artifact.data, media_type=artifact.ref.content_type, headers=_HEADERS)


async def _owns(key: str, user_id: UUID, services: ServicesDep) -> bool:
    match = _RUN_KEY.match(key)
    if match is None:
        return False
    try:
        run_id = UUID(match["run_id"])
    except ValueError:
        return False
    async with services.sessions() as s:
        return await run_owner(s, run_id) == user_id
