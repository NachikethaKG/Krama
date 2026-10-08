"""Unit and integration tests for PageObserver capture against Gitea pages."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from app.observer import Observation, ObserverPort, PageObserver
from app.ports.models import Action, ObservedState, StepRef, Target
from app.ports.observer import Observer

pytestmark = pytest.mark.anyio


def test_observer_protocol_conformance() -> None:
    observer = PageObserver()
    # Statically verified against Observer port
    _typed_check: Observer = observer
    assert _typed_check is not None
    assert isinstance(observer, ObserverPort)


async def test_capture_fields_against_mock_gitea(mock_gitea_page: Page) -> None:
    observer = PageObserver()
    observer.attach(mock_gitea_page)

    await mock_gitea_page.goto("http://gitea.local/")

    step1 = StepRef(
        seq=1,
        action=Action(type="navigate", value="/"),
        target=Target(role="main"),
        instruction_text="Navigate to Gitea dashboard",
    )

    obs1: Observation = await observer.capture(mock_gitea_page, step=step1)

    assert isinstance(obs1, ObservedState)
    assert obs1.url == "/"
    assert obs1.raw_url == "http://gitea.local/"
    assert obs1.title == "Dashboard - Gitea"
    assert "Dashboard" in obs1.headings
    assert obs1.aria_snapshot != ""
    assert isinstance(obs1.screenshot, bytes)
    assert obs1.screenshot.startswith(b"\x89PNG")
    assert obs1.network_summary.request_count >= 1

    # Navigate to create repo form with password field
    await mock_gitea_page.goto("http://gitea.local/repo/create")
    step2 = StepRef(
        seq=2,
        action=Action(type="click"),
        target=Target(role="link", name="New Repository"),
        instruction_text="Open repository creation form",
    )

    obs2: Observation = await observer.capture(mock_gitea_page, step=step2)

    assert obs2.url == "/repo/create"
    assert obs2.title == "Create a repository - Gitea"
    assert "Create a repository" in obs2.headings
    assert "Repository Name *" in obs2.aria_snapshot
    # Verify password masking: secrets must never leak in ARIA snapshot
    assert "super-secret-password-123" not in obs2.aria_snapshot
    assert isinstance(obs2.screenshot, bytes)
    assert obs2.screenshot.startswith(b"\x89PNG")


async def test_capture_with_artifact_storage(mock_gitea_page: Page, tmp_path: Path) -> None:
    observer = PageObserver(artifacts_dir=tmp_path)
    observer.attach(mock_gitea_page)
    await mock_gitea_page.goto("http://gitea.local/repo/create")

    step = StepRef(
        seq=4,
        action=Action(type="wait"),
        target=Target(role="main"),
        instruction_text="Wait for form to load",
    )

    obs = await observer.capture(mock_gitea_page, step=step)

    assert obs.screenshot_path is not None
    saved_path_str = obs.screenshot_path

    # Check file exists via asyncio thread to avoid ASYNC240 lint
    def _read_file(p: str) -> bytes:
        return Path(p).read_bytes()

    file_bytes = await asyncio.to_thread(_read_file, saved_path_str)
    assert file_bytes.startswith(b"\x89PNG")


@pytest.mark.gitea
async def test_capture_against_live_gitea(gitea_live_url: str) -> None:
    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=True)
        context: BrowserContext = await browser.new_context(base_url=gitea_live_url)
        page: Page = await context.new_page()

        observer = PageObserver()
        observer.attach(page)
        await page.goto(f"{gitea_live_url}/")

        step = StepRef(
            seq=1,
            action=Action(type="navigate", value="/"),
            target=Target(role="main"),
            instruction_text="Visit live Gitea instance",
        )

        obs = await observer.capture(page, step=step)

        assert obs.url == "/"
        assert isinstance(obs.screenshot, bytes)
        assert obs.screenshot.startswith(b"\x89PNG")
        assert obs.network_summary.request_count >= 1

        await context.close()
        await browser.close()
