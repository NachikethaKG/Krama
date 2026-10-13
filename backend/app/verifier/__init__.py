"""Verifier: decides whether a step reached its `expected_state`, from what was observed before and after it.

`LayeredVerifier` (layered.py) is what runs use; `RuleVerifier` is its exact-rules layer.
"""

from app.verifier.aria import AriaNode, parse_aria_snapshot
from app.verifier.layered import (
    LayeredVerifier,
    NetworkCall,
    StepEvidence,
    StepVerifier,
    VisionJudge,
    VisionVerdict,
)
from app.verifier.verifier import Check, RuleVerifier, ScriptedVerifier, VerificationOutcome, Verifier

__all__ = [
    "AriaNode",
    "Check",
    "LayeredVerifier",
    "NetworkCall",
    "RuleVerifier",
    "ScriptedVerifier",
    "StepEvidence",
    "StepVerifier",
    "VerificationOutcome",
    "Verifier",
    "VisionJudge",
    "VisionVerdict",
    "parse_aria_snapshot",
]
