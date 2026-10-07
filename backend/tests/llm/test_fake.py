import pytest
from pydantic import BaseModel

from app.config import Settings
from app.llm import FakeProvider, FakeResponse, GeminiProvider, LLMError, create_provider
from tests.llm.conftest import PlanOut

pytestmark = pytest.mark.anyio


class Other(BaseModel):
    answer: str


async def test_replays_the_recorded_gitea_plan() -> None:
    provider = FakeProvider.from_dir()

    result = await provider.generate(system="s", prompt="Create demo-repo please", schema=PlanOut)

    assert result.model == "gemini-2.5-flash"
    steps = result.value.steps
    assert [s.action.type for s in steps] == ["click", "fill", "click", "click"]
    assert steps[-1].expected_state.url_matches == "^/demo/demo-repo$"
    assert provider.calls == [("s", "Create demo-repo please", "PlanOut")]


async def test_no_matching_fixture_is_an_error() -> None:
    provider = FakeProvider.from_dir()

    with pytest.raises(LLMError, match="no fake LLM response"):
        await provider.generate(system="s", prompt="delete everything", schema=PlanOut)


async def test_schema_name_filters_fixtures() -> None:
    provider = FakeProvider(
        [
            FakeResponse(name="plan", schema_name="PlanOut", response={"steps": []}),
            FakeResponse(name="other", schema_name="Other", response={"answer": "42"}),
        ]
    )

    result = await provider.generate(system="s", prompt="anything", schema=Other)

    assert result.value.answer == "42"


async def test_fixture_that_breaks_the_schema_is_reported() -> None:
    provider = FakeProvider([FakeResponse(name="broken", response={"answer": 1, "extra": True})])

    with pytest.raises(LLMError, match="fixture 'broken'"):
        await provider.generate(system="s", prompt="p", schema=PlanOut)


def test_factory_uses_fake_by_default() -> None:
    assert isinstance(create_provider(Settings(llm_provider="fake")), FakeProvider)


def test_factory_builds_gemini_when_selected() -> None:
    assert isinstance(create_provider(Settings(llm_provider="gemini", gemini_api_key="k")), GeminiProvider)
