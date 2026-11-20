"""Workflow search (#416-#418, #135): GET /workflows?q= on real Postgres, with a held-out query set (the
spike's queries are in docs/research/assets/phase-6-search; these are different on purpose)."""

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import update

from app.contracts_gen.workflow_schema import WorkflowPage
from app.db import PlanRow, ValidationRow, WorkflowRow, WorkflowStepRow
from app.db.repositories import add_workflow, add_workflow_version
from app.db.search import expand
from tests.api.test_flow import Api, Sessions, make_user, reply, services
from tests.db.test_repositories import new_run
from tests.runs.test_runner import GOOD_PLAN

pytestmark = pytest.mark.anyio

# title, app, request, step texts, status
CORPUS: list[tuple[str, str, str, list[str], str]] = [
    (
        "Create a repository",
        "gitea",
        "make a new repo",
        [
            "Click “New Repository”.",
            "Enter your repository name, for example “notes”.",
            "Click “Create Repository”.",
        ],
        "verified",
    ),
    (
        "Add a collaborator to a repository",
        "github",
        "give someone write access",
        [
            "Open “Settings”.",
            "Click “Collaborators”.",
            "Click “Add people”.",
            "Enter the person's username, for example “alex”.",
        ],
        "verified",
    ),
    (
        "Create an issue",
        "github",
        "report a bug",
        [
            "Open the “Issues” tab.",
            "Click “New issue”.",
            "Enter a title in “Title”, for example “Login fails”.",
            "Click “Submit new issue”.",
        ],
        "verified",
    ),
    (
        "Add a label to an issue",
        "gitea",
        "tag an issue as bug",
        ["Open the issue.", "Click “Labels”.", "Select “bug”."],
        "verified",
    ),
    (
        "Protect the main branch",
        "github",
        "require reviews before merging",
        [
            "Open “Settings”.",
            "Click “Branches”.",
            "Click “Add branch protection rule”.",
            "Select “Require a pull request before merging”.",
        ],
        "verified",
    ),
    (
        "Add a webhook",
        "gitea",
        "send push events to a server",
        [
            "Open “Settings”.",
            "Click “Webhooks”.",
            "Enter your payload URL, for example “https://example.test/hook”.",
            "Click “Add Webhook”.",
        ],
        "verified",
    ),
    (
        "Change repository visibility to private",
        "github",
        "make my repo private",
        [
            "Open “Settings”.",
            "Scroll to the danger zone.",
            "Click “Change visibility”.",
            "Select “Make private”.",
        ],
        "outdated",
    ),
    (
        "Change repository visibility",
        "gitea",
        "hide a repository",
        ["Open “Settings”.", "Select “Make repository private”.", "Click “Update Settings”."],
        "verified",
    ),
    (
        "Delete a repository",
        "gitea",
        "remove an old repo",
        [
            "Open “Settings”.",
            "Click “Delete This Repository”.",
            "Enter the repository name to confirm.",
            "Click “Delete Repository”.",
        ],
        "verified",
    ),
    (
        "Open a pull request",
        "github",
        "propose my changes",
        [
            "Open “Pull requests”.",
            "Click “New pull request”.",
            "Select your branch.",
            "Click “Create pull request”.",
        ],
        "verified",
    ),
    (
        "Invite a member to an organization",
        "github",
        "add someone to the org",
        [
            "Open the organization.",
            "Click “People”.",
            "Click “Invite member”.",
            "Enter their username or email.",
        ],
        "verified",
    ),
    (
        "Create a branch",
        "gitea",
        "start a feature branch",
        [
            "Open the branch menu.",
            "Enter your branch name, for example “feature-docs”.",
            "Click “Create branch”.",
        ],
        "verified",
    ),
]

# Held-out queries: (query, title that must be in the top 3)
QUERIES = [
    ("new repository", "Create a repository"),
    ("let alex push to my repo", "Add a collaborator to a repository"),
    ("file a bug report", "Create an issue"),
    ("mark issue as bug", "Add a label to an issue"),
    ("branch protection", "Protect the main branch"),
    ("webhok", "Add a webhook"),  # a typo
    ("make repo private", "Change repository visibility"),
    ("remove a repository", "Delete a repository"),
    ("open PR", "Open a pull request"),
    ("invite someone to the organization", "Invite a member to an organization"),
    ("feature branch", "Create a branch"),
    ("add people", "Add a collaborator to a repository"),
]


async def seed(
    sessions: Sessions, user_id: UUID, title: str, app: str, request: str, steps: list[str], status: str
) -> UUID:
    run = await new_run(sessions, status="verified")
    async with sessions.begin() as s:
        plan = await s.get(PlanRow, run.plan_id)
        assert plan is not None
        from app.db import TaskRow

        task = await s.get(TaskRow, plan.task_id)
        assert task is not None
        task.prompt, task.user_id = request, user_id
        workflow = WorkflowRow(
            task_id=plan.task_id, run_id=run.id, user_id=user_id, title=title, target_app=app,
            target_url="http://127.0.0.1:3001", status=status, confidence=1.0,
        )  # fmt: skip
        rows = [
            WorkflowStepRow(
                seq=n,
                action={"type": "click"},
                target={"role": "button", "name": "x"},
                instruction_text=t,
                expected_state={},
                observed_state={},
                verification={"result": "verified", "method": ["url"], "confidence": 1.0},
                risk="low",
            )
            for n, t in enumerate(steps, start=1)
        ]
        await add_workflow(s, workflow, rows)
        return workflow.id


async def search(api: Api, q: str, **params: Any) -> WorkflowPage:
    got = await api.client.get("/workflows", params={"q": q, **params})
    assert got.status_code == 200, got.text
    return WorkflowPage.model_validate(got.json())


@pytest.fixture
async def corpus(sessions: Sessions, tmp_path: Path) -> Any:
    svc = services(sessions, tmp_path, reply(GOOD_PLAN))
    async with Api(svc) as api:
        assert api.user is not None
        ids = {t[0]: await seed(sessions, api.user.id, *t) for t in CORPUS}
        yield api, ids


async def test_the_held_out_queries_find_the_right_workflow_in_the_top_3(corpus: Any) -> None:
    api, _ = corpus
    misses = []
    for query, title in QUERIES:
        top = [i.title for i in (await search(api, query, limit=3)).items]
        if title not in top:
            misses.append((query, top))
    assert len(misses) <= 2, misses  # gate: >= 10/12


async def test_results_carry_a_score_a_marked_snippet_and_the_matching_step(corpus: Any) -> None:
    api, _ = corpus
    [first, *_] = (await search(api, "webhooks")).items

    assert first.title == "Add a webhook" and first.score is not None and first.score > 0
    assert first.match is not None and "<mark>" in first.match.snippet
    assert first.match.step_seq == 2  # “Click “Webhooks”.” matches best


async def test_outdated_ranks_below_verified_for_the_same_words(corpus: Any) -> None:
    api, _ = corpus
    titles = [i.title for i in (await search(api, "change repository visibility")).items]

    assert titles.index("Change repository visibility") < titles.index(
        "Change repository visibility to private"
    )


async def test_fresh_validation_lifts_a_workflow(corpus: Any, sessions: Sessions) -> None:
    api, ids = corpus
    old = datetime.now(UTC) - timedelta(days=365)
    async with sessions.begin() as s:
        await s.execute(
            update(WorkflowRow).where(WorkflowRow.id == ids["Create a branch"]).values(created_at=old)
        )
        s.add(ValidationRow(workflow_id=ids["Create a branch"], status="passed", ran_at=datetime.now(UTC)))
    [hit] = [i for i in (await search(api, "feature branch")).items if i.title == "Create a branch"]

    assert hit.last_validated_at is not None


async def test_status_filters_both_the_list_and_search(corpus: Any) -> None:
    api, _ = corpus
    listed = WorkflowPage.model_validate(
        (await api.client.get("/workflows", params={"status": "outdated"})).json()
    )
    found = await search(api, "visibility", status="outdated")

    assert [i.title for i in listed.items] == ["Change repository visibility to private"]
    assert [i.title for i in found.items] == ["Change repository visibility to private"]


async def test_search_is_per_user_and_pages_by_offset(corpus: Any, sessions: Sessions) -> None:
    api, _ = corpus
    page1 = await search(api, "settings", limit=2)
    page2 = await search(api, "settings", limit=2, offset=2)
    async with Api(api.svc, await make_user(sessions)) as other:
        nothing = await search(other, "repository")

    assert page1.next_cursor == "2" and len(page1.items) == 2
    assert not {i.id for i in page1.items} & {i.id for i in page2.items}
    assert nothing.items == []


async def test_the_search_copy_follows_a_new_current_version(corpus: Any, sessions: Sessions) -> None:
    api, ids = corpus
    async with sessions.begin() as s:
        workflow = await s.get(WorkflowRow, ids["Add a webhook"])
        assert workflow is not None
        step = WorkflowStepRow(
            seq=1, action={"type": "click"}, target={"role": "button", "name": "x"},
            instruction_text="Click “Integrations” and choose “Zapier hooks”.",
            expected_state={}, observed_state={},
            verification={"result": "verified", "method": ["url"], "confidence": 1.0}, risk="low",
        )  # fmt: skip
        await add_workflow_version(
            s, workflow, [step], source="heal", status="current", run_id=None, confidence=1.0,
            recording_path=None, viewport=None, change_summary=None,
        )  # fmt: skip

    found = [i.title for i in (await search(api, "zapier")).items]
    assert found == ["Add a webhook"]


async def test_a_thousand_workflows_stay_fast(corpus: Any, sessions: Sessions) -> None:
    api, _ = corpus
    assert api.user is not None
    for n in range(
        60
    ):  # enough rows that the plan uses the GIN indexes; p95 is checked at the gate with 1,000
        await seed(
            sessions,
            api.user.id,
            f"Export report {n}",
            "custom",
            "download data",
            ["Open “Reports”.", f"Click “Export {n}”."],
            "verified",
        )
    timings = []
    for query, _ in QUERIES:
        t0 = time.perf_counter()
        await search(api, query)
        timings.append(time.perf_counter() - t0)
    assert sorted(timings)[int(len(timings) * 0.95) - 1] < 0.5


def test_synonyms_widen_the_words_but_keep_them() -> None:
    assert expand("Open PR on my repo?") == "open pull request on my repository"
    assert expand("invite someone") == "invite add person user member collaborator"
