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
from app.db.llm_calls import DbCallSink
from app.export import ArqExportQueue, InProcessExportQueue
from app.llm import GeminiProvider, LLMProvider, create_provider
from app.llm.recording import RecordingProvider
from app.llm.translator import LLMTranslator
from app.observer import PageObserver
from app.planner import LLMPlanner
from app.planner.planner import Planner
from app.planner.service import PlanningService
from app.planner.stepwise import OutlinePlanner, StepDecider
from app.policy import LLMClassifier, PolicyService
from app.ports import ExportQueue
from app.runs import InProcessExecutor, RunEnvironment, RunStore
from app.runs.events import EventHub, RedisEventRelay
from app.runs.profiles import ProfileStore
from app.runs.queue import ArqExecutor
from app.runs.takeover import ScreenFeed
from app.runs.translations import TranslationService
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
    translations: TranslationService | None = None
    """Tutorials in other languages (#422)."""
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
        if self.translations is not None:
            await self.translations.shutdown()
        if self.relay is not None:
            await self.relay.stop()
        if isinstance(self.exports, (InProcessExportQueue, ArqExportQueue)):
            await self.exports.shutdown()
        if self.engine is not None:
            await self.engine.dispose()


def recorded_provider(settings: Settings, sessions: async_sessionmaker[AsyncSession]) -> LLMProvider:
    """The configured provider; with a real one (not the fake), every request is recorded in `llm_calls`."""
    llm = create_provider(settings)
    if settings.llm_provider == "fake":
        return llm
    return RecordingProvider(llm, DbCallSink(sessions), provider=settings.llm_provider)


def step_provider(settings: Settings, sessions: async_sessionmaker[AsyncSession] | None) -> LLMProvider:
    """The provider for step-mode decisions: Gemini with its own model order (Q1), else the configured one."""
    if settings.llm_provider != "gemini":
        return create_provider(settings) if sessions is None else recorded_provider(settings, sessions)
    llm: LLMProvider = GeminiProvider(
        settings.gemini_api_key, settings.gemini_step_model_list or settings.gemini_model_list
    )
    return llm if sessions is None else RecordingProvider(llm, DbCallSink(sessions), provider="gemini")


def plan_maker(settings: Settings, llm: LLMProvider) -> Planner:
    """The planner for new tasks: an outline (step mode, ADR 0011) or every step up front (until v1.4)."""
    return OutlinePlanner(llm) if settings.planner_mode == "steps" else LLMPlanner(llm)


def build_run_environment(
    settings: Settings, sessions: async_sessionmaker[AsyncSession] | None = None
) -> RunEnvironment:
    """What a run needs (verifier, observer, policy, planner for replans, ...), the same in the API process
    and in the worker (#95). With `sessions`, every LLM request is recorded (#464)."""
    llm = create_provider(settings) if sessions is None else recorded_provider(settings, sessions)
    # Vision needs Gemini: the gemini provider, or groq with a Gemini key for its images (SplitProvider).
    gemini = settings.llm_provider == "gemini" or (
        settings.llm_provider == "groq" and bool(settings.gemini_api_key)
    )
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
        decider=StepDecider(step_provider(settings, sessions)),
        target=lambda job: target_setup(job.target_url, settings),
        run_timeout_s=settings.run_timeout_seconds,
        max_replans_per_run=settings.max_replans_per_run,
        # One LLM call after the last step: did the steps do the whole task (#274)? Gemini only, like vision.
        # Text only, so the local development model can answer it too (ADR 0010); step mode leans on it.
        task_check=GeminiTaskChecker(llm) if settings.llm_provider in ("gemini", "ollama", "groq") else None,
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
    llm = recorded_provider(settings, sessions)
    policy = PolicyService(classifier=LLMClassifier(llm))
    executor: InProcessExecutor | ArqExecutor
    relay: RedisEventRelay | None = None
    exports: ExportQueue
    if settings.run_executor == "arq":
        # Exports render in the worker too, on their own queue, one at a time (D14).
        exports = ArqExportQueue(settings.redis_url)
    else:
        exports = InProcessExportQueue(
            sessions,
            LocalFsStore(settings.artifacts_dir),
            timeout_s=settings.export_timeout_seconds,
            localize=TranslationService(sessions, LLMTranslator(llm)).localize,
        )
    if settings.run_executor == "arq":
        # Runs execute in the worker (`just backend worker`); its events come back over Redis (#95).
        executor = ArqExecutor(store, settings.redis_url, artifacts_dir=settings.artifacts_dir)
        relay = RedisEventRelay(settings.redis_url, hub)
    profiles = ProfileStore(sessions, settings.krama_storage_key.get_secret_value())
    if settings.run_executor != "arq":
        env = build_run_environment(settings, sessions)
        env.profiles = profiles
        executor = InProcessExecutor(store, env, max_concurrent=settings.max_concurrent_runs)
    return Services(
        sessions=sessions,
        hub=hub,
        store=store,
        executor=executor,
        planning=PlanningService(
            sessions,
            plan_maker(settings, llm),
            lambda url: target_setup(url, settings),
            policy=policy,
            profiles=profiles,
        ),
        engine=engine,
        target=lambda url: target_setup(url, settings),
        relay=relay,
        exports=exports,
        profiles=profiles,
        sites={"gitea": settings.gitea_url, "github": settings.github_url},
        translations=TranslationService(sessions, LLMTranslator(llm)),
    )


def get_services(request: Request) -> Services:
    services: Services = request.app.state.services
    return services


ServicesDep = Annotated[Services, Depends(get_services)]
