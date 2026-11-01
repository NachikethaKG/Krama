"""Interfaces between backend modules owned by different people (docs/adr/0001-ownership-by-module.md).

Changing anything here is a contract change: both owners review. Implementations never import each
other's modules; they only depend on these protocols and their value types.
"""

from app.ports.artifacts import ArtifactFiles, ArtifactStore
from app.ports.exports import (
    ExportJobInput,
    ExportNotFoundError,
    ExportQueue,
    ExportStateError,
    ExportStore,
)
from app.ports.models import (
    ArtifactInfo,
    ArtifactNotFoundError,
    ArtifactRef,
    InvalidArtifactKeyError,
    ObservedState,
    PageState,
    PlanDraft,
    PolicyDecision,
    RecordingRef,
    RiskReport,
    StepRef,
    StepRisk,
    StoredArtifact,
)
from app.ports.narration import (
    NarrationClip,
    NarrationError,
    NarrationLine,
    NarrationManifest,
    Narrator,
    SceneTiming,
    plan_scenes,
)
from app.ports.observer import Observer
from app.ports.policy import Policy

__all__ = [
    "ArtifactFiles",
    "ArtifactInfo",
    "ArtifactNotFoundError",
    "ArtifactRef",
    "ArtifactStore",
    "ExportJobInput",
    "ExportNotFoundError",
    "ExportQueue",
    "ExportStateError",
    "ExportStore",
    "InvalidArtifactKeyError",
    "NarrationClip",
    "NarrationError",
    "NarrationLine",
    "NarrationManifest",
    "Narrator",
    "ObservedState",
    "Observer",
    "PageState",
    "PlanDraft",
    "Policy",
    "PolicyDecision",
    "RecordingRef",
    "RiskReport",
    "SceneTiming",
    "StepRef",
    "StepRisk",
    "StoredArtifact",
    "plan_scenes",
]
