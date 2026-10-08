"""Verification script for Gemini API quota and structured output parsing.

Checks Gemini structured JSON response schema enforcement, logs latency and token usage,
and handles HTTP 429 quota exceptions cleanly.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field


class StepVerification(BaseModel):
    """Schema enforcing structured output for an action step verification."""

    step_name: str = Field(description="Name or label of the action step")
    action_type: str = Field(
        description="Type of action, e.g. click, fill, navigate, verify"
    )
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(description="Brief explanation of the action rationale")


def _get_api_key() -> str:
    """Retrieve GEMINI_API_KEY from environment or repo-root .env file."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if api_key:
        return api_key

    # Attempt fallback to repo-root .env file
    repo_root = Path(__file__).resolve().parents[2]
    env_file = repo_root / ".env"
    if env_file.is_file():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("GEMINI_API_KEY=") and not line.startswith("#"):
                    parsed_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if parsed_key:
                        return parsed_key
        except OSError:
            pass

    return ""


def run_verification(model: str = "gemini-2.5-flash") -> dict[str, Any]:
    """Execute a structured-output verification call against Gemini API."""
    api_key = _get_api_key()
    if not api_key:
        print(
            "ERROR: GEMINI_API_KEY is not set.\n"
            "Please export GEMINI_API_KEY in your environment or set GEMINI_API_KEY in the repo-root .env file.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"[*] Initializing genai.Client with model: {model}")
    client = genai.Client(api_key=api_key)

    prompt = (
        "Verify the step 'Click New Repository button on dashboard' for browser automation in Gitea. "
        "Return structured verification data."
    )

    config = types.GenerateContentConfig(
        system_instruction="You are an autonomous browser agent verifying UI actions.",
        temperature=0.0,
        response_mime_type="application/json",
        response_json_schema=StepVerification.model_json_schema(),
    )

    t0 = time.perf_counter()
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
        latency_ms = round((time.perf_counter() - t0) * 1000)

        # Parse and validate structured output
        raw_text = response.text or "{}"
        structured_step = StepVerification.model_validate_json(raw_text)

        usage = response.usage_metadata
        token_usage: dict[str, int | None] = {
            "prompt_tokens": usage.prompt_token_count if usage else None,
            "candidates_tokens": usage.candidates_token_count if usage else None,
            "total_tokens": usage.total_token_count if usage else None,
        }

        result: dict[str, Any] = {
            "status": "success",
            "model": model,
            "latency_ms": latency_ms,
            "token_usage": token_usage,
            "data": structured_step.model_dump(),
        }

        print("[+] Call successful:")
        print(json.dumps(result, indent=2))
        return result

    except errors.APIError as e:
        latency_ms = round((time.perf_counter() - t0) * 1000)
        if e.code == 429:
            print(
                f"[-] HTTP 429 Quota Exceeded after {latency_ms} ms: {e.message}",
                file=sys.stderr,
            )
            err_result: dict[str, Any] = {
                "status": "rate_limited",
                "http_code": 429,
                "model": model,
                "latency_ms": latency_ms,
                "error_message": str(e.message),
            }
            print(json.dumps(err_result, indent=2), file=sys.stderr)
            return err_result

        print(
            f"[-] API Error {e.code} ({e.status}) after {latency_ms} ms: {e.message}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    target_model = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    )
    run_verification(model=target_model)
