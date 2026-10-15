"""Lightweight LLM classifier fallback for ambiguous actions and contextual disambiguation."""

import asyncio
import json
import logging
import re
from typing import Any, Protocol

from app.policy.models import ActionContext, RiskAssessment, RiskLevel

logger = logging.getLogger(__name__)

CLASSIFIER_SYSTEM_PROMPT = (
    "You are a browser agent safety classifier.\n"
    "Evaluate the proposed action and page context, and classify its risk into:\n"
    '- "low": Read-only actions, viewing, navigation, creating benign items, or non-destructive operations '
    "like discarding unsaved drafts or resetting search filters.\n"
    '- "medium": Reversible state changes '
    "(closing issues, renaming branches, locking comments, signing out).\n"
    '- "high": Irreversible destructive actions (deleting repositories, branches, databases, or accounts), '
    "transferring assets/ownership, changing security credentials/passwords/keys, financial transactions, "
    "or publishing live content.\n\n"
    "Return ONLY a JSON object with:\n"
    "{\n"
    '  "level": "low" | "medium" | "high",\n'
    '  "reason": "concise explanation of why this risk level was selected",\n'
    '  "confidence": 0.0 to 1.0\n'
    "}"
)


class LLMCallable(Protocol):
    """Protocol for an LLM generator or callable."""

    async def __call__(self, prompt: str, system: str | None = None) -> str: ...


class LLMClassifier:
    """Classifies ambiguous actions using an LLM, with timeout and safe fallback."""

    def __init__(
        self,
        llm: Any | None = None,
        *,
        timeout_s: float = 3.0,
        fallback_level: RiskLevel = RiskLevel.HIGH,
    ) -> None:
        self._llm = llm
        self.timeout_s = timeout_s
        self.fallback_level = fallback_level

    async def classify(
        self,
        action_summary: str,
        context: ActionContext | None = None,
    ) -> RiskAssessment:
        """Classify an ambiguous action with the LLM or heuristic fallback."""
        ctx_dict: dict[str, Any] = {}
        if context:
            if context.url:
                ctx_dict["url"] = context.url
            if context.title:
                ctx_dict["title"] = context.title
            if context.dialog_text:
                ctx_dict["dialog_text"] = context.dialog_text
            if context.previous_step:
                ctx_dict["previous_step"] = context.previous_step
            if context.aria_excerpt:
                ctx_dict["aria_excerpt"] = context.aria_excerpt[:500]

        prompt = (
            f"Action: {action_summary}\n"
            f"Context: {json.dumps(ctx_dict) if ctx_dict else 'None'}\n\n"
            "Classify the risk level as JSON."
        )

        if self._llm is None:
            return self._heuristic_fallback(action_summary, context)

        try:
            raw_response = await asyncio.wait_for(
                self._invoke_llm(prompt, CLASSIFIER_SYSTEM_PROMPT),
                timeout=self.timeout_s,
            )
            return self._parse_response(raw_response)
        except TimeoutError:
            logger.warning(
                "LLM risk classifier timed out after %g s on '%s'; failing safely to %s",
                self.timeout_s,
                action_summary,
                self.fallback_level.value,
            )
            return RiskAssessment(
                level=self.fallback_level,
                reason=f"LLM classifier timed out after {self.timeout_s}s; safe fallback",
                flagged_by="fallback_safe",
                confidence=1.0,
                matched_rule="timeout_safe_fallback",
            )
        except Exception as e:
            logger.warning(
                "LLM risk classifier error on '%s': %s; failing safely to %s",
                action_summary,
                e,
                self.fallback_level.value,
            )
            return RiskAssessment(
                level=self.fallback_level,
                reason=f"LLM classifier API error ({type(e).__name__}: {e}); safe fallback",
                flagged_by="fallback_safe",
                confidence=1.0,
                matched_rule="error_safe_fallback",
            )

    async def _invoke_llm(self, prompt: str, system: str) -> str:
        """Call the underlying LLM object across supported invocation signatures."""
        llm = self._llm
        if llm is None:
            raise RuntimeError("Cannot invoke LLM when llm is None")

        if callable(llm):
            try:
                res = llm(prompt, system=system)
            except TypeError:
                res = llm(prompt)
            if asyncio.iscoroutine(res):
                return str(await res)
            return str(res)

        if hasattr(llm, "generate") and callable(llm.generate):
            generate_fn = llm.generate
            res = generate_fn(prompt=prompt, system=system)
            val = await res if asyncio.iscoroutine(res) else res
            if hasattr(val, "value"):
                inner = val.value
                if hasattr(inner, "model_dump"):
                    return json.dumps(inner.model_dump(mode="json"))
                return str(inner)
            return str(val)

        raise TypeError(f"Unsupported LLM provider type: {type(llm)}")

    def _parse_response(self, text: str) -> RiskAssessment:
        """Parse structured JSON from model output."""
        cleaned = text.strip()
        # Strip Markdown code fences if present
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        data = json.loads(cleaned)
        level_str = str(data.get("level", self.fallback_level.value)).lower().strip()
        try:
            level = RiskLevel(level_str)
        except ValueError:
            level = self.fallback_level

        reason = str(data.get("reason", "Classified by LLM"))
        conf = float(data.get("confidence", 1.0))

        return RiskAssessment(
            level=level,
            reason=reason,
            flagged_by="llm_classifier",
            confidence=conf,
            matched_rule="llm_disambiguation",
        )

    def _heuristic_fallback(
        self,
        action_summary: str,
        context: ActionContext | None,
    ) -> RiskAssessment:
        """Deterministic heuristic for common disambiguation cases when no LLM is provided."""
        low = action_summary.lower()
        if "draft" in low:
            return RiskAssessment(
                level=RiskLevel.LOW,
                reason="Discarding unsaved draft is non-destructive to repository data",
                flagged_by="llm_classifier",
                confidence=0.9,
                matched_rule="heuristic_draft_low",
            )
        if any(term in low for term in ("filter", "zoom", "view")):
            return RiskAssessment(
                level=RiskLevel.LOW,
                reason="Resetting UI view or filter state",
                flagged_by="llm_classifier",
                confidence=0.95,
                matched_rule="heuristic_view_low",
            )
        if "feedback" in low or "ping" in low:
            return RiskAssessment(
                level=RiskLevel.LOW,
                reason="Sending non-transactional user feedback or ping",
                flagged_by="llm_classifier",
                confidence=0.9,
                matched_rule="heuristic_feedback_low",
            )
        # If ambiguous and we can't safely declare it low:
        return RiskAssessment(
            level=self.fallback_level,
            reason=f"Ambiguous action '{action_summary}' without LLM; failing safely",
            flagged_by="fallback_safe",
            confidence=1.0,
            matched_rule="ambiguous_no_llm_safe_fallback",
        )
