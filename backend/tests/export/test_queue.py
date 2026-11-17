"""Unit tests for ArqExportQueue (#126)."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.export.queue import EXPORT_JOB, EXPORT_QUEUE, ArqExportQueue, export_job_id

pytestmark = pytest.mark.anyio


async def test_arq_export_queue_enqueues_with_correct_parameters() -> None:
    queue = ArqExportQueue("redis://localhost:6379/0")
    export_id = uuid4()

    mock_redis = AsyncMock()
    with patch.object(queue, "_redis", return_value=mock_redis):
        await queue.enqueue(export_id)

    mock_redis.enqueue_job.assert_awaited_once_with(
        EXPORT_JOB,
        str(export_id),
        _queue_name=EXPORT_QUEUE,
        _job_id=export_job_id(export_id),
    )


async def test_arq_export_queue_shutdown() -> None:
    queue = ArqExportQueue("redis://localhost:6379/0")
    mock_pool = AsyncMock()
    queue._pool = mock_pool

    await queue.shutdown()
    mock_pool.aclose.assert_awaited_once()
    assert queue._pool is None
