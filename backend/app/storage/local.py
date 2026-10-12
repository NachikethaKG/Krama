"""`ArtifactStore` on the local disk (`ARTIFACTS_DIR`, default `data/artifacts`). S3/MinIO comes later."""

import asyncio
import os
import tempfile
from pathlib import Path

from app.ports.models import (
    ArtifactContentType,
    ArtifactNotFoundError,
    ArtifactRef,
    InvalidArtifactKeyError,
    StoredArtifact,
    validate_artifact_key,
)

_PNG = b"\x89PNG\r\n\x1a\n"
_JPEG = b"\xff\xd8\xff"


class LocalFsStore:
    """Artifacts as files under `root`, one file per key. Content type is read back from the bytes."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    async def put(self, key: str, data: bytes, content_type: ArtifactContentType) -> ArtifactRef:
        path = self._path(key)
        await asyncio.to_thread(_write_atomically, path, data)
        return ArtifactRef(key=key, content_type=content_type, size_bytes=len(data))

    async def get(self, key: str) -> StoredArtifact:
        path = self._path(key)
        try:
            data = await asyncio.to_thread(path.read_bytes)
        except (FileNotFoundError, IsADirectoryError, NotADirectoryError, PermissionError):
            # PermissionError: on Windows, reading a directory raises it instead of IsADirectoryError.
            raise ArtifactNotFoundError(key) from None
        ref = ArtifactRef(key=key, content_type=sniff_content_type(data), size_bytes=len(data))
        return StoredArtifact(ref=ref, data=data)

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._path(key).is_file)

    def _path(self, key: str) -> Path:
        path = (self.root / validate_artifact_key(key)).resolve()
        # The key is already safe; this also stops a symlink inside the store from pointing outside it.
        if not path.is_relative_to(self.root):
            raise InvalidArtifactKeyError(f"artifact key escapes the store: {key!r}")
        return path


def sniff_content_type(data: bytes) -> ArtifactContentType:
    """png and jpeg by their signature; everything else is served as JSON (never as HTML or SVG)."""
    if data.startswith(_PNG):
        return "image/png"
    if data.startswith(_JPEG):
        return "image/jpeg"
    return "application/json"


def _write_atomically(path: Path, data: bytes) -> None:
    """Readers see the old file or the new one, never half a screenshot."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
