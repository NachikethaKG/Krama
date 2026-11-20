"""Workflow search (#418, #135): Postgres full text + trigrams, ranked by text x status x freshness.

Decisions S1-S6 (docs/research/phase-6-decisions-alignment.md; spike in docs/research/assets/phase-6-search):
- candidates: any query word in the weighted `search` vector (title and app > request > step text), or the
  query as a trigram word-match anywhere in `search_text` (typos, partial words);
- text = 0.7 * cover-density rank + 0.3 * trigram word-similarity to the title, x1.5 when every word matches
  (the spike's "all words first", in one query so offset paging stays stable);
- status: verified 1.0, auto-updated (a heal made the current version) 0.95, outdated 0.6, else 0.3;
- freshness: 0.8 + 0.2 * e^(-days since the last validation (else creation) / 30);
- a small general synonym map widens the words (repo -> repository, ...).
The snippet is the best-matching step line (or the title) with `<mark>` around matched words. It is plain text
from the page and the request: show it as text plus marks, never as HTML.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

MAX_QUERY = 200

SYNONYMS = {
    "repo": "repository",
    "repos": "repositories",
    "pr": "pull request",
    "prs": "pull requests",
    "someone": "person user member collaborator",
    "invite": "invite add",
    "access": "access collaborator member",
    "tag": "label",
    "private": "private visibility",
    "public": "public visibility",
    "remove": "remove delete",
    "erase": "delete",
}
"""General words people use for the same thing; not tuned per workflow (S4)."""


@dataclass(frozen=True)
class SearchHit:
    workflow_id: UUID
    score: float
    step_seq: int | None
    snippet: str
    last_validated_at: datetime | None


def expand(query: str) -> str:
    """The query in lower case with synonyms added (the original words stay)."""
    words = re.findall(r"[\w'-]+", query.lower())
    return " ".join(SYNONYMS.get(w, w) for w in words)


_ANY_WORD = (
    "to_tsquery('simple', coalesce(nullif("
    "array_to_string(tsvector_to_array(to_tsvector('english', :q)), ' | '), ''), 'xx_no_words'))"
)

_SQL = f"""
WITH q AS (SELECT {_ANY_WORD} AS q, websearch_to_tsquery('english', :q) AS every),
v AS (SELECT workflow_id, max(ran_at) AS last FROM validations GROUP BY workflow_id)
SELECT w.id,
  (0.7 * ts_rank_cd(w.search, q.q, 32) + 0.3 * word_similarity(:raw, w.title))
  * CASE WHEN w.search @@ q.every THEN 1.5 ELSE 1.0 END
  * CASE WHEN w.status = 'verified' AND coalesce(cv.source, 'initial') <> 'heal' THEN 1.0
         WHEN w.status = 'verified' THEN 0.95
         WHEN w.status = 'outdated' THEN 0.6
         ELSE 0.3 END
  * (0.8 + 0.2 * exp(-extract(epoch FROM (now() - coalesce(v.last, w.created_at))) / 86400.0 / 30.0))
    AS score,
  best.n AS step_n,
  ts_headline(w.lang, coalesce(best.t, w.title), q.q,
              'StartSel=<mark>, StopSel=</mark>, MaxWords=24, MinWords=6, ShortWord=2') AS snippet,
  v.last AS last_validated_at
FROM workflows w
CROSS JOIN q
LEFT JOIN v ON v.workflow_id = w.id
LEFT JOIN workflow_versions cv ON cv.id = w.current_version_id
LEFT JOIN LATERAL (
  SELECT s.t, s.n FROM unnest(string_to_array(w.search_steps, E'\\n')) WITH ORDINALITY AS s(t, n)
  WHERE to_tsvector(w.lang, s.t) @@ q.q
  ORDER BY ts_rank(to_tsvector(w.lang, s.t), q.q) DESC, s.n
  LIMIT 1
) best ON true
WHERE w.user_id = :user_id
  AND (w.search @@ q.q OR :raw <% w.search_text)
  {{status}}
ORDER BY score DESC, w.id
LIMIT :limit OFFSET :offset
"""


async def search_workflows(
    session: AsyncSession,
    *,
    user_id: UUID,
    query: str,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[SearchHit]:
    """The user's workflows matching `query`, best first."""
    raw = " ".join(query.split())[:MAX_QUERY].lower()
    if not raw:
        return []
    sql = _SQL.replace("{status}", "AND w.status = :status" if status is not None else "")
    params: dict[str, object] = {
        "q": expand(raw), "raw": raw, "user_id": user_id, "limit": limit, "offset": offset,
    }  # fmt: skip
    if status is not None:
        params["status"] = status
    rows = (await session.execute(text(sql), params)).all()
    return [
        SearchHit(
            workflow_id=r.id,
            score=round(float(r.score), 4),
            step_seq=int(r.step_n) if r.step_n is not None else None,
            snippet=r.snippet,
            last_validated_at=r.last_validated_at,
        )
        for r in rows
    ]


async def last_validated(session: AsyncSession, workflow_ids: Sequence[UUID]) -> dict[UUID, datetime]:
    """When validation last checked each workflow (the list shows it too)."""
    if not workflow_ids:
        return {}
    rows = await session.execute(
        text(
            "SELECT workflow_id, max(ran_at) FROM validations"
            " WHERE workflow_id = ANY(:ids) GROUP BY workflow_id"
        ),
        {"ids": list(workflow_ids)},
    )
    return {wid: last for wid, last in rows.all()}
