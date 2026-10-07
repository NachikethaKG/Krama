import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from app.llm.base import LLMAttempt, LLMError, LLMResult

DEFAULT_FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "llm_fixtures"


class FakeResponse(BaseModel):
    """One recorded reply. It is used when every `prompt_contains` string is in the prompt and, if `schema`
    is set, the requested schema's class name matches."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    schema_name: str | None = None
    prompt_contains: list[str] = []
    model: str = "fake"
    response: Any


class FakeProvider:
    """Replays recorded replies: free, offline, deterministic. Used by tests and CI (`LLM_PROVIDER=fake`)."""

    def __init__(self, responses: Sequence[FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str, str]] = []
        """(system, prompt, schema name) of every call, for assertions in tests."""

    @classmethod
    def from_dir(cls, fixtures_dir: Path = DEFAULT_FIXTURES_DIR) -> "FakeProvider":
        files = sorted(fixtures_dir.glob("*.json"))
        return cls([FakeResponse.model_validate(json.loads(f.read_text(encoding="utf-8"))) for f in files])

    async def generate[M: BaseModel](self, *, system: str, prompt: str, schema: type[M]) -> LLMResult[M]:
        self.calls.append((system, prompt, schema.__name__))
        for r in self._responses:
            if r.schema_name not in (None, schema.__name__):
                continue
            if all(s in prompt for s in r.prompt_contains):
                try:
                    value = schema.model_validate(r.response)
                except ValidationError as e:
                    # A fixture that doesn't match the schema is a broken fixture, not a model mistake.
                    raise LLMError(
                        f"fixture {r.name!r} does not validate against {schema.__name__}: {e}"
                    ) from e
                attempt = LLMAttempt(model=r.model, status="ok", latency_ms=0)
                return LLMResult[M](value=value, model=r.model, attempts=[attempt])
        raise LLMError(f"no fake LLM response matches schema {schema.__name__} and this prompt")
