"""What we know about a target site before planning or running on it: hints, and how to sign in.

Phase 1 knows one site, the local Gitea (signed in as the demo user). Phase 3 adds GitHub and stored
browser sessions (#87).
"""

from dataclasses import dataclass, field

from app.agent.gitea_create_repo import login_steps
from app.agent.runlog import ScriptedStep
from app.config import Settings


@dataclass(frozen=True)
class TargetSetup:
    site: str | None = None
    """Key into the planner's SITE_HINTS."""
    preconditions: list[ScriptedStep] = field(default_factory=list)
    """Run before planning and before step 1 (e.g. signing in). Never part of the plan or the recording."""
    signed_in_as: str | None = None


def target_setup(target_url: str, settings: Settings) -> TargetSetup:
    if _same_origin(target_url, settings.gitea_url):
        user = settings.gitea_demo_user
        return TargetSetup(
            site="gitea",
            preconditions=login_steps(user=user, password=settings.gitea_demo_password),
            signed_in_as=user,
        )
    return TargetSetup()


def _same_origin(a: str, b: str) -> bool:
    def norm(url: str) -> str:
        return url.rstrip("/").lower().replace("://127.0.0.1", "://localhost")

    return norm(a) == norm(b)
