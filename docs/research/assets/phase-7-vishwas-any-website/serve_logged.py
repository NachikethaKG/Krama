"""Phase 7 spike (#457): start the API with every LLM call logged to a JSONL file.

Each line: time, schema name, model, status per attempt, latency, tokens, whether an image was sent, and the
prompt (page-derived text from public sites only; no secrets). Run from backend/:

    uv run python <path>/serve_logged.py <log.jsonl>
"""

import json
import sys
import time
from pathlib import Path
from typing import Any

import uvicorn
from pydantic import BaseModel

import app.api.services as services
import app.llm as llm
from app.config import Settings
from app.llm import LLMError, LLMProvider, LLMResult

LOG = Path(sys.argv[1]).resolve()
_create = llm.create_provider


class LoggedProvider:
    def __init__(self, inner: LLMProvider) -> None:
        self._inner = inner

    async def generate[M: BaseModel](
        self, *, system: str, prompt: str, schema: type[M], image: bytes | None = None
    ) -> LLMResult[M]:
        t0 = time.time()
        entry: dict[str, Any] = {
            "t": round(t0, 1),
            "schema": schema.__name__,
            "image": image is not None,
            "prompt_chars": len(prompt),
            "system_chars": len(system),
            "prompt": prompt,
        }
        try:
            result = await self._inner.generate(system=system, prompt=prompt, schema=schema, image=image)
        except LLMError as e:
            entry |= {"ok": False, "error": str(e), "attempts": [a.model_dump() for a in e.attempts]}
            _write(entry, t0)
            raise
        entry |= {
            "ok": True,
            "model": result.model,
            "attempts": [a.model_dump() for a in result.attempts],
            "reply": result.value.model_dump(mode="json"),
        }
        _write(entry, t0)
        return result


def _write(entry: dict[str, Any], t0: float) -> None:
    entry["seconds"] = round(time.time() - t0, 1)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def create_logged(settings: Settings) -> LLMProvider:
    return LoggedProvider(_create(settings))


llm.create_provider = create_logged
services.create_provider = create_logged  # type: ignore[attr-defined]

if __name__ == "__main__":
    from app.main import app

    uvicorn.run(app, host="127.0.0.1", port=8000, loop="app.dev_loop:factory")
