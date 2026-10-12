from typing import Protocol

from app.ports.models import ArtifactContentType, ArtifactRef, StoredArtifact


class ArtifactStore(Protocol):
    """Stores run artifacts (screenshots, rrweb JSON). Implemented by `app.storage` (Vishwas), used by
    `app.observer` (Nachiketha) and served read-only at `GET /api/v1/artifacts/{key}`.

    Keys are relative POSIX paths checked by `validate_artifact_key`. The store never looks inside the bytes:
    callers mask sensitive content BEFORE `put` (AGENTS.md §4).
    """

    async def put(self, key: str, data: bytes, content_type: ArtifactContentType) -> ArtifactRef:
        """Store `data` under `key`, replacing any artifact already there.

        Raises InvalidArtifactKeyError for an unsafe key.
        """
        ...

    async def get(self, key: str) -> StoredArtifact:
        """Read an artifact back.

        Raises ArtifactNotFoundError, or InvalidArtifactKeyError for an unsafe key.
        """
        ...

    async def exists(self, key: str) -> bool:
        """Whether an artifact is stored under `key`. Raises InvalidArtifactKeyError for an unsafe key."""
        ...
