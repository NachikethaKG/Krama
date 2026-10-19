import json
import re
from pathlib import Path

from app.api.guide import guide_markdown
from app.contracts_gen.workflow_schema import Workflow

FIXTURE = Path(__file__).resolve().parents[3] / "contracts" / "fixtures" / "gitea-create-repo-workflow.json"


def workflow(**changes: object) -> Workflow:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return Workflow.model_validate(data | changes)


def url(key: str) -> str:
    return f"http://api.test/api/v1/artifacts/{key}"


def test_steps_are_numbered_with_the_tutorial_text_and_a_screenshot_each() -> None:
    wf = workflow()

    guide = guide_markdown(wf, url)

    lines = guide.splitlines()
    assert lines[0] == "# Create a repository in local Gitea"
    numbered = [line for line in lines if line[:1].isdigit()]
    assert numbered == [f"{i}. {s.instruction_text}" for i, s in enumerate(wf.steps, start=1)]
    for i, s in enumerate(wf.steps, start=1):
        assert f"   ![Step {i}]({url(s.screenshot_path or '')})" in lines
    assert "Verified on gitea" in guide and "5 steps" in guide


def test_steps_follow_seq_and_a_step_without_screenshot_has_no_image() -> None:
    wf = workflow()
    steps = list(reversed(wf.steps))
    steps[0] = steps[0].model_copy(update={"screenshot_path": None})  # the last step (seq 5)

    guide = guide_markdown(wf.model_copy(update={"steps": steps}), url)

    assert guide.index("1. Open the + menu") < guide.index("5. Click Create Repository")
    assert "![Step 5]" not in guide and guide.count("![Step") == 4


def test_page_text_cannot_add_links_images_or_html() -> None:
    wf = workflow()
    evil = "Click “[here](javascript:alert(1))” <img src=x onerror=alert(1)> ![x](http://evil)"
    steps = [wf.steps[0].model_copy(update={"instruction_text": evil})]

    guide = guide_markdown(wf.model_copy(update={"steps": steps, "title": "# Title\n<script>"}), url)

    # Every syntax character is backslash-escaped (CommonMark shows it as text): nothing unescaped is left.
    for raw in (r"(?<!\\)\[here", r"(?<!\\)<img", r"(?<!\\)<script", r"(?<!\\)!\[x"):
        assert not re.search(raw, guide), raw
    assert r"\[here\](javascript:alert(1))" in guide and r"\<img src=x onerror=alert(1)\>" in guide
    assert guide.splitlines()[0] == r"# \# Title \<script\>"
