"""GET /workflows/{id}/versions (#108): a verified run stores its workflow as version 1, and the workflow's
`revision` names the version whose steps it returns."""

from pathlib import Path

import pytest

from app.contracts_gen.workflow_schema import Workflow, WorkflowVersionList
from tests.api.test_flow import Api, Sessions, reply, services
from tests.api.test_reverify import verified_workflow
from tests.runs.test_runner import GOOD_PLAN

pytestmark = pytest.mark.anyio


async def test_a_verified_run_stores_version_1(sessions: Sessions, tmp_path: Path, site: str) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        workflow_id = await verified_workflow(api, site)

        response = await api.client.get(f"/workflows/{workflow_id}/versions")
        workflow = Workflow.model_validate((await api.client.get(f"/workflows/{workflow_id}")).json())

    assert response.status_code == 200, response.text
    [version] = WorkflowVersionList.model_validate(response.json()).items
    assert (version.revision, version.source, version.status) == (1, "initial", "current")
    assert version.workflow_id == workflow_id and version.run_id == workflow.run_id
    assert version.step_count == len(workflow.steps) == 4
    assert version.parent_version_id is None and version.change_summary is None
    assert workflow.revision == 1


async def test_versions_of_an_unknown_workflow_are_404(sessions: Sessions, tmp_path: Path) -> None:
    async with Api(services(sessions, tmp_path)) as api:
        response = await api.client.get("/workflows/6f1c2a4e-1111-4b8a-9a1b-123456789abc/versions")

    assert response.status_code == 404 and response.json()["error"]["code"] == "not_found"
