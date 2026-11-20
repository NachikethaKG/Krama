"""The API's composition root: builds the real services once at startup, hands them to routes as a dependency.

This is the one place that picks the concrete classes behind the ports (observer, LLM, vision), as `cli.py`
does for `krama run`. Tests build `Services` themselves with fakes where the architecture allows it.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.agent.healer import GeminiHealChooser
from app.agent.quota import RedisHealBudget
from app.agent.vision import GeminiVisionLocator
from app.config import Settings
from app.db import create_engine, create_sessionmaker
from app.export import ArqExportQueue, InProcessExportQueue
from app.llm import create_provider
from app.observer import PageObserver
from app.planner import LLMPlanner
from app.planner.service import PlanningService
from app.policy import LLMClassifier, PolicyService
from app.ports import ExportQueue
from app.runs import InProcessExecutor, RunEnvironment, RunStore
from app.runs.events import EventHub, RedisEventRelay
from app.runs.profiles import ProfileStore
from app.runs.queue import ArqExecutor
from app.runs.takeover import ScreenFeed
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
    executor: "InProcessExecutor | ArqExecutor"
    planning: PlanningService
    engine: AsyncEngine | None = None
    target: Callable[[str], TargetSetup] = field(default=lambda _url: TargetSetup())
    """What we know about a target URL: hints, sign-in, and its reset for reverify (#77)."""
    relay: "RedisEventRelay | None" = None
    """With the arq worker: wakes the live-view streams when the worker commits an event."""
    screens: dict[UUID, ScreenFeed] = field(default_factory=dict)
    profiles: ProfileStore | None = None
    """Each user's own site sessions (ADR 0007)."""
    sites: dict[str, str] = field(default_factory=dict)
    """Site key -> URL, for sign-in runs (gitea, github)."""
    """Active takeovers' frame feeds, by run (ADR 0008): filled by POST /takeover, read by WS /screen."""
    exports: ExportQueue | None = None
    """Where `POST /workflows/{id}/exports` sends exports: the arq worker, or the API itself. None in tests
    that override the queue dependency."""

    async def start(self) -> None:
        # In-process: a restart leaves queued/running runs without a browser, so they fail honestly. With the
        # worker, the worker does this for its own runs (an API restart doesn't touch a running browser).
        await self.executor.recover()
        if self.relay is not None:
            await self.relay.start()
        if isinstance(self.exports, InProcessExportQueue):
            await self.exports.recover()  # with the worker, the worker recovers its own exports

    async def close(self) -> None:
        await self.planning.shutdown()
        await self.executor.shutdown()
        if self.relay is not None:
            await self.relay.stop()
        if isinstance(self.exports, (InProcessExportQueue, ArqExportQueue)):
            await self.exports.shutdown()
        if self.engine is not None:
            await self.engine.dispose()


def build_run_environment(settings: Settings) -> RunEnvironment:
    """What a run needs (verifier, observer, policy, planner for replans, ...), the same in the API process
    and in the worker (#95)."""
    llm = create_provider(settings)
    gemini = settings.llm_provider == "gemini"
    policy = PolicyService(classifier=LLMClassifier(llm))
    store_ = LocalFsStore(settings.artifacts_dir)
    return RunEnvironment(
        # Vision costs real Gemini quota; with the fake LLM the cheaper layers decide alone.
        verifier=LayeredVerifier(GeminiVisionJudge(llm) if gemini else None),
        # Screenshots and the rrweb recording go through the ArtifactStore port (#50), keyed by run.
        observer_for=lambda run_id: PageObserver(artifact_store=store_, run_id=str(run_id)),
        artifacts_dir=settings.artifacts_dir,
        artifacts=store_,
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
        # Self-healing (#112): Gemini chooses among the candidates only when scoring can't decide, within a
        # daily budget shared through Redis (D12).
        heal_chooser=GeminiHealChooser(llm) if gemini else None,
        heal_budget=RedisHealBudget(settings.redis_url),
    )


def build_services(settings: Settings) -> Services:
    engine = create_engine(settings.database_url)
    sessions = create_sessionmaker(engine)
    hub = EventHub()
    store = RunStore(sessions, on_event=hub.notify)
    llm = create_provider(settings)
    policy = PolicyService(classifier=LLMClassifier(llm))
    executor: InProcessExecutor | ArqExecutor
    relay: RedisEventRelay | None = None
    exports: ExportQueue
    if settings.run_executor == "arq":
        # Exports render in the worker too, on their own queue, one at a time (D14).
        exports = ArqExportQueue(settings.redis_url)
    else:
        exports = InProcessExportQueue(
            sessions, LocalFsStore(settings.artifacts_dir), timeout_s=settings.export_timeout_seconds
        )
    if settings.run_executor == "arq":
        # Runs execute in the worker (`just backend worker`); its events come back over Redis (#95).
        executor = ArqExecutor(store, settings.redis_url, artifacts_dir=settings.artifacts_dir)
        relay = RedisEventRelay(settings.redis_url, hub)
    profiles = ProfileStore(sessions, settings.krama_storage_key.get_secret_value())
    if settings.run_executor != "arq":
        env = build_run_environment(settings)
        env.profiles = profiles
        executor = InProcessExecutor(store, env, max_concurrent=settings.max_concurrent_runs)
    return Services(
        sessions=sessions,
        hub=hub,
        store=store,
        executor=executor,
        planning=PlanningService(
            sessions, LLMPlanner(llm), lambda url: target_setup(url, settings), policy=policy
        ),
        engine=engine,
        target=lambda url: target_setup(url, settings),
        relay=relay,
        exports=exports,
        profiles=profiles,
        sites={"gitea": settings.gitea_url, "github": settings.github_url},
    )


def get_services(request: Request) -> Services:
    services: Services = request.app.state.services
    return services


ServicesDep = Annotated[Services, Depends(get_services)]
