from pathlib import Path
from typing import Protocol

from app.ports.models import ArtifactContentType, ArtifactInfo, ArtifactRef, StoredArtifact


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


class ArtifactFiles(Protocol):
    """File operations for large artifacts: exported videos and narration clips (Phase 5, D20).

    A separate protocol so `ArtifactStore` implementations stay valid on their own. `LocalFsStore` implements
    both (#124). With object storage later (docs/adr/0005), `local_path` becomes a download to a local cache
    or a presigned URL; callers that serve files must go through it, never build a path themselves.
    """

    async def put_file(self, key: str, path: Path, content_type: ArtifactContentType) -> ArtifactRef:
        """Copy the finished file at `path` into the store under `key`, replacing what is there. The caller
        still owns `path` (and deletes its temporary file).

        Raises InvalidArtifactKeyError or FileNotFoundError.
        """
        ...

    async def local_path(self, key: str) -> Path:
        """A local file with the artifact's bytes, for `FileResponse` (HTTP Range). Don't write to it.

        Raises ArtifactNotFoundError, or InvalidArtifactKeyError for an unsafe key.
        """
        ...

    async def delete(self, key: str) -> bool:
        """Delete one artifact. True if it existed. Raises InvalidArtifactKeyError for an unsafe key."""
        ...

    async def list(self, prefix: str) -> list[ArtifactInfo]:
        """Every artifact whose key starts with the folder `prefix` (e.g. `exports/` or `narration/<voice>/`),
        sorted by key. `prefix` must be a safe key ending in `/`, else InvalidArtifactKeyError."""
        ...
