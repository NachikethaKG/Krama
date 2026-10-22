"""The API's composition root: builds the real services once at startup, hands them to routes as a dependency.

This is the one place that picks the concrete classes behind the ports (observer, LLM, vision), as `cli.py`
does for `krama run`. Tests build `Services` themselves with fakes where the architecture allows it.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
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
from app.policy import LLMClassifier, PolicyService
from app.runs import InProcessExecutor, RunEnvironment, RunStore
from app.runs.events import EventHub
from app.storage import LocalFsStore
from app.targets import TargetSetup, target_setup
from app.verifier import LayeredVerifier
from app.verifier.task_check import GeminiTaskChecker
from app.verifier.vision import GeminiVisionJudge


@dataclass
class Services:
    sessions: async_sessionmaker[AsyncSession]
    hub: EventHub
    store: RunStore
    executor: InProcessExecutor
    planning: PlanningService
    engine: AsyncEngine | None = None
    target: Callable[[str], TargetSetup] = field(default=lambda _url: TargetSetup())
    """What we know about a target URL: hints, sign-in, and its reset for reverify (#77)."""

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
    gemini = settings.llm_provider == "gemini"
    policy = PolicyService(classifier=LLMClassifier(llm))
    store_ = LocalFsStore(settings.artifacts_dir)
    env = RunEnvironment(
        # Vision costs real Gemini quota; with the fake LLM the cheaper layers decide alone.
        verifier=LayeredVerifier(GeminiVisionJudge(llm) if gemini else None),
        # Screenshots and the rrweb recording go through the ArtifactStore port (#50), keyed by run.
        observer_for=lambda run_id: PageObserver(artifact_store=store_, run_id=str(run_id)),
        artifacts_dir=settings.artifacts_dir,
        preconditions=lambda job: target_setup(job.target_url, settings).preconditions,
        vision=GeminiVisionLocator(llm) if gemini else None,
        # Checked before every step (#59): denylist + LLM classifier for unclear cases, CAPTCHA / bot-wall /
        # login-wall stop, secret masking. The executor also pauses every step the plan marks high risk.
        policy=policy,
        planner=LLMPlanner(llm),
        target=lambda job: target_setup(job.target_url, settings),
        run_timeout_s=settings.run_timeout_seconds,
        max_replans_per_run=settings.max_replans_per_run,
        # One LLM call after the last step: did the steps do the whole task (#274)? Gemini only, like vision.
        task_check=GeminiTaskChecker(llm) if gemini else None,
    )
    return Services(
        sessions=sessions,
        hub=hub,
        store=store,
        executor=InProcessExecutor(store, env, max_concurrent=settings.max_concurrent_runs),
        planning=PlanningService(
            sessions, LLMPlanner(llm), lambda url: target_setup(url, settings), policy=policy
        ),
        engine=engine,
        target=lambda url: target_setup(url, settings),
    )


def get_services(request: Request) -> Services:
    services: Services = request.app.state.services
    return services


ServicesDep = Annotated[Services, Depends(get_services)]
