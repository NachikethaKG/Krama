from pathlib import Path

import pytest

from app.config import REPO_ROOT, Settings


def test_relative_artifacts_dir_resolves_against_repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTIFACTS_DIR", "./data/artifacts")

    assert Settings().artifacts_dir == REPO_ROOT / "data" / "artifacts"


def test_absolute_artifacts_dir_is_kept(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path))

    assert Settings().artifacts_dir == tmp_path
