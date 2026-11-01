import os
from pathlib import Path

import pytest

from app.ports import ArtifactNotFoundError, ArtifactRef, InvalidArtifactKeyError
from app.storage import LocalFsStore, sniff_content_type

pytestmark = pytest.mark.anyio

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
KEY = "runs/6f1c2a4e-1111-4b8a-9a1b-123456789abc/steps/1-after.png"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def test_put_get_round_trip(tmp_path: Path) -> None:
    store = LocalFsStore(tmp_path)

    ref = await store.put(KEY, PNG, "image/png")
    stored = await store.get(KEY)

    assert ref == ArtifactRef(key=KEY, content_type="image/png", size_bytes=len(PNG))
    assert stored.ref == ref and stored.data == PNG
    assert (tmp_path / KEY).read_bytes() == PNG  # a plain file under the root, same relative path
    assert await store.exists(KEY)


async def test_put_overwrites_and_leaves_no_temp_files(tmp_path: Path) -> None:
    store = LocalFsStore(tmp_path)

    await store.put("runs/r1/recording.json", b'{"events": [1]}', "application/json")
    await store.put("runs/r1/recording.json", b'{"events": [1, 2]}', "application/json")

    assert (await store.get("runs/r1/recording.json")).data == b'{"events": [1, 2]}'
    assert sorted(p.name for p in (tmp_path / "runs" / "r1").iterdir()) == ["recording.json"]


async def test_missing_key_and_directories_are_not_found(tmp_path: Path) -> None:
    store = LocalFsStore(tmp_path)
    await store.put("runs/r1/a.png", PNG, "image/png")

    for key in ("runs/r1/missing.png", "runs/r1", "runs"):
        assert not await store.exists(key)
        with pytest.raises(ArtifactNotFoundError):
            await store.get(key)


@pytest.mark.parametrize("key", ["../outside.png", "/etc/passwd", r"runs\..\x.png", "C:/x.png", "runs//x"])
async def test_unsafe_keys_never_touch_the_disk(tmp_path: Path, key: str) -> None:
    store = LocalFsStore(tmp_path / "store")

    with pytest.raises(InvalidArtifactKeyError):
        await store.put(key, PNG, "image/png")
    with pytest.raises(InvalidArtifactKeyError):
        await store.get(key)
    assert not (tmp_path / "outside.png").exists()


async def test_a_symlink_cannot_lead_out_of_the_store(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.json").write_text("{}", encoding="utf-8")
    root = tmp_path / "store"
    root.mkdir()
    try:
        os.symlink(outside, root / "link", target_is_directory=True)
    except OSError:
        pytest.skip("creating symlinks needs Developer Mode or admin rights on Windows")

    with pytest.raises(InvalidArtifactKeyError, match="escapes"):
        await LocalFsStore(root).get("link/secret.json")


@pytest.mark.parametrize(
    ("data", "content_type"),
    [(PNG, "image/png"), (b"\xff\xd8\xff\xe0rest", "image/jpeg"), (b"[]", "application/json"),
     (b"<html><script>alert(1)</script>", "application/json"),
     (b"RIFF\x24\x00\x00\x00WAVEfmt ", "audio/wav"), (b"RIFF\x24\x00\x00\x00AVI LIST", "application/json"),
     (b"\x00\x00\x00\x20ftypisom\x00\x00", "video/mp4"),
     (b"WEBVTT\n\n00:00.000 --> 00:01.000\nHi", "text/vtt"), (b"\xef\xbb\xbfWEBVTT\r\n", "text/vtt"),
     (b"WEBVTTX", "application/json")],
)  # fmt: skip
def test_content_type_comes_from_the_bytes(data: bytes, content_type: str) -> None:
    assert sniff_content_type(data) == content_type


# --- ArtifactFiles (Phase 5): put_file, local_path, delete, list ---


async def test_put_file_copies_and_local_path_serves_it(tmp_path: Path) -> None:
    store = LocalFsStore(tmp_path / "store")
    source = tmp_path / "render.mp4"
    source.write_bytes(b"\x00\x00\x00\x20ftypisom" + b"x" * 1000)

    ref = await store.put_file("exports/e1.mp4", source, "video/mp4")
    path = await store.local_path("exports/e1.mp4")

    assert ref.size_bytes == source.stat().st_size
    assert path.read_bytes() == source.read_bytes() and source.exists()  # the caller still owns its file
    assert path.is_relative_to((tmp_path / "store").resolve())
    assert not [p for p in path.parent.iterdir() if p.name.endswith(".tmp")]


async def test_put_file_of_a_missing_source_leaves_nothing(tmp_path: Path) -> None:
    store = LocalFsStore(tmp_path)
    with pytest.raises(FileNotFoundError):
        await store.put_file("exports/e1.mp4", tmp_path / "nope.mp4", "video/mp4")
    assert not await store.exists("exports/e1.mp4")
    assert not list((tmp_path / "exports").iterdir())


async def test_local_path_of_missing_or_folder_is_not_found(tmp_path: Path) -> None:
    store = LocalFsStore(tmp_path)
    await store.put("exports/sub/a.mp4", b"1", "video/mp4")
    for key in ("exports/none.mp4", "exports/sub"):
        with pytest.raises(ArtifactNotFoundError):
            await store.local_path(key)


async def test_delete(tmp_path: Path) -> None:
    store = LocalFsStore(tmp_path)
    await store.put("exports/sub/a.mp4", b"1", "video/mp4")
    assert await store.delete("exports/sub/a.mp4") is True
    assert await store.delete("exports/sub/a.mp4") is False
    assert await store.delete("exports/sub") is False  # a folder is never an artifact
    with pytest.raises(InvalidArtifactKeyError):
        await store.delete("../outside.txt")


async def test_list_a_folder(tmp_path: Path) -> None:
    store = LocalFsStore(tmp_path)
    for key in ("exports/b.mp4", "exports/a/x.vtt", "exportsX/c.mp4", "narration/v/1.wav"):
        await store.put(key, b"1234", "video/mp4")
    (tmp_path / "exports" / ".b.mp4.123.tmp").write_bytes(b"half")  # a write in progress

    listed = await store.list("exports/")

    assert [i.key for i in listed] == ["exports/a/x.vtt", "exports/b.mp4"]
    assert all(i.size_bytes == 4 and i.modified_at.tzinfo is not None for i in listed)
    assert await store.list("nothing/") == []
    with pytest.raises(InvalidArtifactKeyError):
        await store.list("exports")
