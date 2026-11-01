"""`ArtifactStore` + `ArtifactFiles` on the local disk (`ARTIFACTS_DIR`, default `data/artifacts`).

Object storage (SeaweedFS) comes later, behind the same ports (docs/adr/0005)."""

import asyncio
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from app.ports.models import (
    ArtifactContentType,
    ArtifactInfo,
    ArtifactNotFoundError,
    ArtifactRef,
    InvalidArtifactKeyError,
    StoredArtifact,
    validate_artifact_key,
    validate_artifact_prefix,
)

_PNG = b"\x89PNG\r\n\x1a\n"
_JPEG = b"\xff\xd8\xff"
_UTF8_BOM = b"\xef\xbb\xbf"


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

    async def put_file(self, key: str, path: Path, content_type: ArtifactContentType) -> ArtifactRef:
        target = self._path(key)
        size = await asyncio.to_thread(_copy_atomically, path, target)
        return ArtifactRef(key=key, content_type=content_type, size_bytes=size)

    async def local_path(self, key: str) -> Path:
        path = self._path(key)
        if not await asyncio.to_thread(path.is_file):
            raise ArtifactNotFoundError(key)
        return path

    async def delete(self, key: str) -> bool:
        path = self._path(key)
        try:
            await asyncio.to_thread(path.unlink)
        except FileNotFoundError:
            return False
        except (IsADirectoryError, PermissionError):
            # A folder is never an artifact (on Windows unlinking one raises PermissionError).
            if await asyncio.to_thread(path.is_dir):
                return False
            raise
        return True

    async def list(self, prefix: str) -> list[ArtifactInfo]:
        folder = self._path(validate_artifact_prefix(prefix)[:-1])
        return await asyncio.to_thread(_list_files, self.root, folder)

    def _path(self, key: str) -> Path:
        path = (self.root / validate_artifact_key(key)).resolve()
        # The key is already safe; this also stops a symlink inside the store from pointing outside it.
        if not path.is_relative_to(self.root):
            raise InvalidArtifactKeyError(f"artifact key escapes the store: {key!r}")
        return path


def sniff_content_type(data: bytes) -> ArtifactContentType:
    """By signature: png, jpeg, wav, mp4, WebVTT. Everything else is served as JSON (never as HTML or SVG)."""
    if data.startswith(_PNG):
        return "image/png"
    if data.startswith(_JPEG):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "audio/wav"
    if data[4:8] == b"ftyp":  # ISO base media file: the first box is `ftyp`
        return "video/mp4"
    text = data.removeprefix(_UTF8_BOM)
    if text.startswith(b"WEBVTT") and text[6:7] in (b"", b"\n", b"\r", b" ", b"\t"):
        return "text/vtt"
    return "application/json"


def _list_files(root: Path, folder: Path) -> list[ArtifactInfo]:
    """Every file under `folder` as an artifact of the store at `root`."""
    if not folder.is_dir():
        return []
    out = []
    for path in folder.rglob("*"):
        if not path.is_file() or path.name.startswith("."):  # half-written temp files start with a dot
            continue
        key = path.relative_to(root).as_posix()
        try:
            validate_artifact_key(key)
        except InvalidArtifactKeyError:
            continue  # not something we wrote
        stat = path.stat()
        out.append(
            ArtifactInfo(
                key=key,
                size_bytes=stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime, UTC),
            )
        )
    return sorted(out, key=lambda i: i.key)


def _copy_atomically(source: Path, path: Path) -> int:
    """Like `_write_atomically`, from a file: videos are copied in chunks, never read into memory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    os.close(fd)
    try:
        shutil.copyfile(source, tmp)
        size = os.path.getsize(tmp)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return size


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
