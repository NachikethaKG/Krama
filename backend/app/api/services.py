"""The API's composition root: builds the real services once at startup, hands them to routes as a dependency.

This is the one place that picks the concrete classes behind the ports (observer, LLM, vision), as `cli.py`
does for `krama run`. Tests build `Services` themselves with fakes where the architecture allows it.
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.agent.vision import GeminiVisionLocator
from app.config import Settings
from app.db import create_engine, create_sessionmaker
from app.llm import create_provider
from app.observer import PageObserver
from app.planner import LLMPlanner
from app.planner.service import PlanningService
from app.runs import InProcessExecutor, RunEnvironment, RunStore
from app.runs.events import EventHub
from app.targets import target_setup
from app.verifier import RuleVerifier


@dataclass
class Services:
    sessions: async_sessionmaker[AsyncSession]
    hub: EventHub
    store: RunStore
    executor: InProcessExecutor
    planning: PlanningService
    engine: AsyncEngine | None = None

    async def start(self) -> None:
        # A restart leaves queued/running runs without a browser: fail them honestly.
        await self.executor.recover()

    async def close(self) -> None:
        await self.planning.shutdown()
        await self.executor.shutdown()
        if self.engine is not None:
            await self.engine.dispose()


def build_services(settings: Settings) -> Services:
    engine = create_engine(settings.database_url)
    sessions = create_sessionmaker(engine)
    hub = EventHub()
    store = RunStore(sessions, on_event=hub.notify)
    llm = create_provider(settings)
    env = RunEnvironment(
        verifier=RuleVerifier(),
        observer_for=lambda run_id: PageObserver(artifacts_dir=settings.artifacts_dir / "runs" / str(run_id)),
        artifacts_dir=settings.artifacts_dir,
        preconditions=lambda job: target_setup(job.target_url, settings).preconditions,
        # Vision costs real Gemini quota; with the fake LLM the chain stops at role/label/text/selector.
        vision=GeminiVisionLocator(llm) if settings.llm_provider == "gemini" else None,
    )
    return Services(
        sessions=sessions,
        hub=hub,
        store=store,
        executor=InProcessExecutor(store, env, max_concurrent=settings.max_concurrent_runs),
        planning=PlanningService(sessions, LLMPlanner(llm), lambda url: target_setup(url, settings)),
        engine=engine,
    )


def get_services(request: Request) -> Services:
    services: Services = request.app.state.services
    return services


ServicesDep = Annotated[Services, Depends(get_services)]
