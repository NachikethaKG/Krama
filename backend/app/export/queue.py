"""Queue producer for video export jobs (#126).

Implements the `ExportQueue` port (app/ports/exports.py) using arq and Redis.
Enqueues jobs to the dedicated arq queue `krama:exports` (decision D14).
"""

import asyncio
from collections.abc import Callable
from uuid import UUID

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ports.artifacts import ArtifactFiles
from app.ports.exports import ExportQueue
from app.ports.narration import Narrator
from app.runs.exports import DbExportStore, recover_exports
from app.tts import get_narrator

from .job import run_export
from .renderer import RemotionRenderer, VideoRenderer

EXPORT_JOB = "export_job"
EXPORT_QUEUE = "krama:exports"


def redis_settings(url: str) -> RedisSettings:
    return RedisSettings.from_dsn(url)


def export_job_id(export_id: UUID) -> str:
    return f"export:{export_id}"


class ArqExportQueue(ExportQueue):
    """Enqueues export requests to the arq worker pool."""

    def __init__(self, redis_url: str) -> None:
        self._url = redis_url
        self._pool: ArqRedis | None = None

    async def _redis(self) -> ArqRedis:
        if self._pool is None:
            self._pool = await create_pool(redis_settings(self._url))
        return self._pool

    async def enqueue(self, export_id: UUID) -> None:
        redis = await self._redis()
        await redis.enqueue_job(
            EXPORT_JOB,
            str(export_id),
            _queue_name=EXPORT_QUEUE,
            _job_id=export_job_id(export_id),
        )

    async def shutdown(self) -> None:
        if self._pool is not None:
            await self._pool.aclose()
            self._pool = None


class InProcessExportQueue:
    """Renders exports inside the API process, one at a time (RUN_EXECUTOR=inprocess, no worker running).

    Same job as the arq worker (`render_export`). `recover()` at startup fails exports a previous process left
    `rendering` and queues the `queued` ones again; `shutdown()` cancels what is running (it fails as
    `interrupted` on the next start).
    """

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        files: ArtifactFiles,
        *,
        timeout_s: float,
        narrator: Callable[[], Narrator] = get_narrator,
        renderer: Callable[[], VideoRenderer] = RemotionRenderer,
    ) -> None:
        self.sessions = sessions
        self.files = files
        self.timeout_s = timeout_s
        self._narrator = narrator
        self._renderer = renderer
        self._one_at_a_time = asyncio.Lock()
        self._tasks: set[asyncio.Task[None]] = set()

    async def enqueue(self, export_id: UUID) -> None:
        task = asyncio.create_task(self._run(export_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def recover(self) -> None:
        for export_id in await recover_exports(self.sessions):
            await self.enqueue(export_id)

    async def wait(self) -> None:
        """Until every queued export has finished (tests)."""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def shutdown(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def _run(self, export_id: UUID) -> None:
        store = DbExportStore(self.sessions)
        async with self._one_at_a_time:
            await run_export(
                export_id,
                store=store,
                files=self.files,
                narrator=self._narrator(),
                renderer=self._renderer(),
                timeout_s=self.timeout_s,
            )
