import pytest
from playwright.async_api import async_playwright

from app.agent.healer import ElementFingerprint
from app.db.models import WorkflowRow, WorkflowStepRow
from app.runs.healer_runner import HealerRunner


@pytest.mark.anyio
async def test_healer_runner_happy_path_deterministic():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        html = """
        <!DOCTYPE html>
        <html>
        <body>
          <form action="/repo/create">
            <button id="btn-create" type="button" onclick="window.location.href = '/repo/done'">
              Create repository
            </button>
          </form>
        </body>
        </html>
        """

        async def handle_route(route):
            if route.request.url.endswith("/repo/done"):
                await route.fulfill(
                    status=200, content_type="text/html", body="<html><body><h1>Done</h1></body></html>"
                )
            else:
                await route.fulfill(status=200, content_type="text/html", body=html)

        await page.route("http://krama.test/**", handle_route)
        await page.goto("http://krama.test/repo/create")

        workflow = WorkflowRow(
            title="Create a repository",
            target_app="gitea",
            target_url="http://krama.test",
            status="verified",
            revision=1,
        )

        step1 = WorkflowStepRow(
            seq=1,
            action={"type": "click"},
            target={"role": "button", "name": "New repo", "selector": "#old-broken-btn"},
            instruction_text="Click Create repository",
            expected_state={"url_matches": "/repo/done"},
            observed_state={},
            verification={"result": "verified"},
            risk="low",
        )

        runner = HealerRunner(page, score_threshold=0.85, margin_threshold=0.15)
        stored_fp = ElementFingerprint(
            role="button",
            name="New repo",
            form_signature="/repo/create|",
            attrs={"id": "btn-create"},
        )

        outcome = await runner.run(
            workflow=workflow,
            steps=[step1],
            failing_seq=1,
            stored_fp=stored_fp,
        )

        assert outcome.ok is True
        assert outcome.trial_verified is True
        assert outcome.all_steps_verified is True
        assert outcome.validation_status == "healed"
        assert outcome.version_status == "current"
        assert outcome.healed_target is not None
        assert outcome.healed_target["name"] == "Create repository"
        assert outcome.change_summary is not None
        assert outcome.change_summary["changes"][0]["category"] == "behaviour"

        await browser.close()


@pytest.mark.anyio
async def test_healer_runner_safety_rejection_on_failed_post_condition():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Button clicks, but DOES NOT navigate/update URL to expected /repo/done
        html = """
        <!DOCTYPE html>
        <html>
        <body>
          <form action="/repo/create">
            <button id="btn-create" type="button">
              Create repository
            </button>
          </form>
        </body>
        </html>
        """
        await page.set_content(html)

        workflow = WorkflowRow(
            title="Create a repository",
            target_app="gitea",
            target_url="http://localhost:3001",
            status="verified",
            revision=1,
        )

        step1 = WorkflowStepRow(
            seq=1,
            action={"type": "click"},
            target={"role": "button", "name": "New repo", "selector": "#old-broken-btn"},
            instruction_text="Click Create repository",
            expected_state={"url_matches": "/repo/done"},
            observed_state={},
            verification={"result": "verified"},
            risk="low",
        )

        runner = HealerRunner(page, score_threshold=0.85, margin_threshold=0.15)
        stored_fp = ElementFingerprint(
            role="button",
            name="New repo",
            form_signature="/repo/create|",
            attrs={"id": "btn-create"},
        )

        outcome = await runner.run(
            workflow=workflow,
            steps=[step1],
            failing_seq=1,
            stored_fp=stored_fp,
        )

        # Safety check MUST reject the candidate because expected URL was not reached
        assert outcome.ok is False
        assert outcome.trial_verified is False
        assert outcome.validation_status == "outdated"
        assert "Safety check failed" in outcome.reason

        await browser.close()


@pytest.mark.anyio
async def test_healer_runner_subsequent_step_failure_discards_heal():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        page.set_default_timeout(2_000)

        html = """
        <!DOCTYPE html>
        <html>
        <body>
          <form action="/repo/create">
            <button id="btn-create" type="button" onclick="window.location.href = '/repo/done'">
              Create repository
            </button>
          </form>
        </body>
        </html>
        """

        async def handle_route(route):
            if route.request.url.endswith("/repo/done"):
                await route.fulfill(
                    status=200, content_type="text/html", body="<html><body><h1>Done</h1></body></html>"
                )
            else:
                await route.fulfill(status=200, content_type="text/html", body=html)

        await page.route("http://krama.test/**", handle_route)
        await page.goto("http://krama.test/repo/create")

        workflow = WorkflowRow(
            title="Create a repository",
            target_app="gitea",
            target_url="http://krama.test",
            status="verified",
            revision=1,
        )

        step1 = WorkflowStepRow(
            seq=1,
            action={"type": "click"},
            target={"role": "button", "name": "New repo", "selector": "#old-broken-btn"},
            instruction_text="Click Create repository",
            expected_state={"url_matches": "/repo/done"},
            observed_state={},
            verification={"result": "verified"},
            risk="low",
        )

        step2 = WorkflowStepRow(
            seq=2,
            action={"type": "click"},
            target={"role": "button", "name": "Nonexistent second step"},
            instruction_text="Click second step",
            expected_state=None,
            observed_state={},
            verification={"result": "verified"},
            risk="low",
        )

        runner = HealerRunner(page, score_threshold=0.85, margin_threshold=0.15)
        stored_fp = ElementFingerprint(
            role="button",
            name="New repo",
            form_signature="/repo/create|",
            attrs={"id": "btn-create"},
        )

        outcome = await runner.run(
            workflow=workflow,
            steps=[step1, step2],
            failing_seq=1,
            stored_fp=stored_fp,
        )

        # Step 1 succeeded, but step 2 failed -> flow has changed -> discard heal!
        assert outcome.ok is False
        assert outcome.trial_verified is True
        assert outcome.all_steps_verified is False
        assert outcome.validation_status == "outdated"
        assert "Subsequent step 2 failed after heal" in outcome.reason

        await browser.close()
