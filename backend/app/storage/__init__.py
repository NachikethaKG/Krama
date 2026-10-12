"""Artifact storage behind the `ArtifactStore` port (app/ports/artifacts.py)."""

from functools import lru_cache

from app.config import get_settings
from app.ports import ArtifactStore
from app.storage.local import LocalFsStore, sniff_content_type


@lru_cache
def get_artifact_store() -> ArtifactStore:
    """The store for this process (FastAPI dependency; tests override it)."""
    return LocalFsStore(get_settings().artifacts_dir)


def _conforms(store: LocalFsStore) -> ArtifactStore:
    return store  # strict mypy fails here if LocalFsStore drifts from the port


__all__ = ["LocalFsStore", "get_artifact_store", "sniff_content_type"]
