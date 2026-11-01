"""Artifact storage behind the `ArtifactStore` port (app/ports/artifacts.py)."""

from functools import lru_cache

from app.config import get_settings
from app.ports import ArtifactFiles, ArtifactStore
from app.storage.local import LocalFsStore, sniff_content_type


@lru_cache
def get_artifact_store() -> ArtifactStore:
    """The store for this process (FastAPI dependency; tests override it)."""
    return LocalFsStore(get_settings().artifacts_dir)


def get_artifact_files() -> ArtifactFiles:
    """The same local store, seen through its file operations (exports, narration clips)."""
    store = get_artifact_store()
    assert isinstance(store, LocalFsStore)
    return store


def _conforms(store: LocalFsStore) -> ArtifactStore:
    return store  # strict mypy fails here if LocalFsStore drifts from the port


def _conforms_files(store: LocalFsStore) -> ArtifactFiles:
    return store


__all__ = ["LocalFsStore", "get_artifact_files", "get_artifact_store", "sniff_content_type"]
