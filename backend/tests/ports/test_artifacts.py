import pytest
from pydantic import ValidationError

from app.ports import ArtifactNotFoundError, ArtifactRef, InvalidArtifactKeyError
from app.ports.fakes import FakeArtifactStore
from app.ports.models import validate_artifact_key

pytestmark = pytest.mark.anyio

KEY = "runs/6f1c2a4e-1111-4b8a-9a1b-123456789abc/steps/3-after.png"


@pytest.mark.parametrize(
    "key",
    [KEY, "recording.json", "runs/r1/rrweb.json", "a/b.c/d_e-f.JPEG"],
)
def test_safe_keys_are_accepted(key: str) -> None:
    assert validate_artifact_key(key) == key


@pytest.mark.parametrize(
    "key",
    [
        "",
        "/etc/passwd",  # absolute
        "../secrets.env",  # traversal
        "runs/../../x.png",
        "runs/./x.png",
        "runs//x.png",  # empty segment
        "runs/x.png/",  # trailing slash
        "runs\\x.png",  # backslash (Windows separator)
        "C:/Windows/x.png",  # drive letter
        "runs/x .png",  # space
        "runs/%2e%2e/x.png",  # url-encoded traversal
        "runs/x\x00.png",  # NUL
        "a" * 513,  # too long
    ],
)
def test_unsafe_keys_are_rejected(key: str) -> None:
    with pytest.raises(InvalidArtifactKeyError):
        validate_artifact_key(key)


def test_artifact_ref_validates_key_and_content_type() -> None:
    with pytest.raises(ValidationError):
        ArtifactRef(key="../x.png", content_type="image/png", size_bytes=1)
    with pytest.raises(ValidationError):
        ArtifactRef.model_validate({"key": "x.html", "content_type": "text/html", "size_bytes": 1})


async def test_fake_store_round_trips_and_overwrites() -> None:
    store = FakeArtifactStore()

    ref = await store.put(KEY, b"\x89PNG first", "image/png")
    assert ref == ArtifactRef(key=KEY, content_type="image/png", size_bytes=10)
    assert await store.exists(KEY)

    await store.put(KEY, b"second", "image/png")  # a retried capture replaces its own file
    stored = await store.get(KEY)
    assert stored.data == b"second"
    assert stored.ref.size_bytes == 6


async def test_fake_store_reports_missing_and_unsafe_keys() -> None:
    store = FakeArtifactStore()

    assert not await store.exists("runs/r1/missing.png")
    with pytest.raises(ArtifactNotFoundError):
        await store.get("runs/r1/missing.png")
    with pytest.raises(InvalidArtifactKeyError):
        await store.put("../escape.png", b"x", "image/png")
    with pytest.raises(InvalidArtifactKeyError):
        await store.get("../escape.png")
    assert store.artifacts == {}
