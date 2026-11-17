"""Queue producer for video export jobs (#126).

Implements the `ExportQueue` port (app/ports/exports.py) using arq and Redis.
Enqueues jobs to the dedicated arq queue `krama:exports` (decision D14).
"""

from uuid import UUID

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.ports.exports import ExportQueue

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
