"""Sensitive data and secret masking utilities for text, structured data, and LLM prompts."""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[REDACTED]"

# 1. Private keys (PEM headers & bodies)
_PRIVATE_KEY_REGEX = re.compile(
    r"-----BEGIN [A-Z0-9_\- ]*PRIVATE KEY-----(?:[\s\S]*?-----END [A-Z0-9_\- ]*PRIVATE KEY-----|[^\n]*)",
)

# 2. Basic authentication credentials embedded in URLs (handles passwords with @)
_BASIC_AUTH_URL_REGEX = re.compile(
    r"(https?://)([^:\s/@]+):(.+)@([a-zA-Z0-9.-]+(?::[0-9]+)?(?:/[^\s]*)?)",
)

# 3. Bearer tokens and JWTs
_BEARER_TOKEN_REGEX = re.compile(
    r"(?i)\bBearer\s+([A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.?[A-Za-z0-9\-_=]*)",
)
_GENERIC_BEARER_REGEX = re.compile(
    r"(?i)\bBearer\s+([A-Za-z0-9\-_=]{16,})\b",
)
_STANDALONE_JWT_REGEX = re.compile(
    r"\beyJ[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]*\b",
)

# 4. Known vendor-specific token signatures (GitHub, Gitea, OpenAI, AWS, Slack)
_VENDOR_TOKENS_REGEX = re.compile(
    r"\b(?:(?:ghp|gho|ghu|ghs|ghr|ght|gitea)_[A-Za-z0-9_]{16,}|sk-[A-Za-z0-9_\-]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9_\-]{10,})\b"
)

# 5. Key-value formatted secrets (in JSON, YAML, CLI args, key=value strings)
# Uses negative lookahead (?!\s*(?:\[REDACTED\]|\*{3,})) to avoid re-masking already redacted tokens.
_KEY_VALUE_SECRET_REGEX = re.compile(
    r"""(?i)(?P<prefix>['"]?(?:api[_-]?key|access[_-]?token|auth[_-]?token|token|secret|password|passwd|auth|client[_-]?secret|private[_-]?key)['"]?\s*[:=]\s*['"]?)(?!\s*(?:\[REDACTED\]|\*{3,}))(?P<val>[^\s'"\}\],&]{6,})(?P<suffix>['"]?)"""
)

# 6. Browser action instructions filling passwords/credentials
_ACTION_INPUT_SECRET_REGEX = re.compile(
    r"""(?i)(?P<prefix>(?:fill|type|enter|press|set)\w*\s+.*?(?:password|token|secret|passwd|auth)[^\n]*?\s+['"])(?!\s*(?:\[REDACTED\]|\*{3,}))(?P<val>[^'"]+)(?P<suffix>['"])"""
)

# 7. ARIA accessibility tree lines with password/token fields
_ARIA_SECRET_REGEX = re.compile(
    r"""((?:textbox|field|input)\s+"[^"]*(?:password|token|secret|passwd)[^"]*":\s*)(?!\s*(?:\[REDACTED\]|\*{3,}))([^\n]+)""",
    re.IGNORECASE,
)

# 8. URL query parameters with secrets
_URL_QUERY_SECRET_REGEX = re.compile(
    r"""(?i)(?P<prefix>[?&](?:api[_-]?key|access[_-]?token|auth[_-]?token|token|secret|password|passwd|auth)=)(?!\s*(?:\[REDACTED\]|\*{3,}))(?P<val>[^&\s]+)"""
)

_SENSITIVE_KEY_WORDS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "credential",
    "credentials",
    "private_key",
)


def mask_text(text: str, *, extra_secrets: list[str] | set[str] | None = None) -> str:
    """Replace detected tokens, secrets, credentials, and passwords with [REDACTED].

    Scans for:
    - PEM private keys
    - Basic auth in URLs
    - Bearer tokens and JWTs
    - Vendor API keys (GitHub, Gitea, OpenAI, AWS, Slack)
    - Key-value credentials (e.g. password=..., "token": "...")
    - Browser fill/type actions targeting password fields
    - ARIA snapshot text for password/secret fields
    - URL query parameter secrets
    - Any explicitly supplied extra secrets
    """
    if not text:
        return ""

    result = text

    # Redact any caller-specified high-priority secrets first
    if extra_secrets:
        for secret in extra_secrets:
            if secret and len(secret) >= 3:
                result = result.replace(secret, REDACTED)

    # 1. Private keys
    result = _PRIVATE_KEY_REGEX.sub(REDACTED, result)

    # 2. Basic auth credentials in URLs
    result = _BASIC_AUTH_URL_REGEX.sub(r"\1\2:[REDACTED]@\4", result)

    # 3. Bearer tokens and JWTs
    result = _BEARER_TOKEN_REGEX.sub(r"Bearer [REDACTED]", result)
    result = _GENERIC_BEARER_REGEX.sub(r"Bearer [REDACTED]", result)
    result = _STANDALONE_JWT_REGEX.sub(REDACTED, result)

    # 4. Known vendor API tokens
    result = _VENDOR_TOKENS_REGEX.sub(REDACTED, result)

    # 5. Key-value formatted secrets
    result = _KEY_VALUE_SECRET_REGEX.sub(r"\g<prefix>[REDACTED]\g<suffix>", result)

    # 6. Action instructions with typed secrets
    result = _ACTION_INPUT_SECRET_REGEX.sub(r"\g<prefix>[REDACTED]\g<suffix>", result)

    # 7. ARIA accessibility snapshot values
    result = _ARIA_SECRET_REGEX.sub(r"\1[REDACTED]", result)

    # 8. Query parameter secrets
    result = _URL_QUERY_SECRET_REGEX.sub(r"\g<prefix>[REDACTED]", result)

    return result


def is_sensitive_key(key: str) -> bool:
    """Return True if dictionary key name indicates a sensitive credential."""
    normalized = key.lower().replace("-", "_")
    return any(word in normalized for word in _SENSITIVE_KEY_WORDS)


def mask_dict(data: Any, *, extra_secrets: list[str] | set[str] | None = None) -> Any:
    """Recursively scrub sensitive keys and secret values from nested dictionaries and lists."""
    if isinstance(data, dict):
        sanitized: dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(k, str) and is_sensitive_key(k):
                sanitized[k] = REDACTED
            else:
                sanitized[k] = mask_dict(v, extra_secrets=extra_secrets)
        return sanitized

    if isinstance(data, list):
        return [mask_dict(item, extra_secrets=extra_secrets) for item in data]

    if isinstance(data, tuple):
        return tuple(mask_dict(item, extra_secrets=extra_secrets) for item in data)

    if isinstance(data, set):
        return {mask_dict(item, extra_secrets=extra_secrets) for item in data}

    if isinstance(data, str):
        return mask_text(data, extra_secrets=extra_secrets)

    return data


def mask_prompt(
    prompt: str | dict[str, Any],
    *,
    extra_secrets: list[str] | set[str] | None = None,
) -> str | dict[str, Any]:
    """Sanitize prompt text or dictionary payload before passing to an LLM."""
    if isinstance(prompt, str):
        return mask_text(prompt, extra_secrets=extra_secrets)
    result = mask_dict(prompt, extra_secrets=extra_secrets)
    if isinstance(result, dict):
        return result
    return {}
