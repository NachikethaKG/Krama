"""GET /metrics/summary: the last benchmark's summary for the metrics dashboard (#102; docs/api-contract.md).

The benchmark reporter writes `benchmarks/results/summary.json` in the contract's MetricsSummary shape; this
serves that file, checked against the contract. The backend never imports `benchmarks` (AGENTS.md §2,
docs/research/phase-3-decisions-alignment.md §7).
"""

import asyncio

from fastapi import APIRouter
from pydantic import ValidationError

from app.api.auth import CurrentUser
from app.api.errors import ApiException
from app.config import get_settings
from app.contracts_gen.common_schema import ErrorResponse
from app.contracts_gen.metrics_summary_schema import MetricsSummary

router = APIRouter(tags=["metrics"])


@router.get(
    "/metrics/summary",
    responses={404: {"model": ErrorResponse, "description": "No benchmark has written a summary yet"}},
)
async def metrics_summary(_user: CurrentUser) -> MetricsSummary:
    path = get_settings().metrics_summary_path
    try:
        text = await asyncio.to_thread(path.read_text, encoding="utf-8")
    except FileNotFoundError:
        raise ApiException(404, "not_found", "No benchmark summary yet: run a benchmark first") from None
    try:
        return MetricsSummary.model_validate_json(text)
    except ValidationError as e:
        # A summary that breaks the contract is the reporter's bug: say so instead of serving it.
        raise ApiException(500, "internal", "The benchmark summary doesn't match the contract") from e
