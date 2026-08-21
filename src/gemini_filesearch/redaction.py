from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Iterable


_PROVIDER_SECRET_PATTERNS = (
    (
        re.compile(r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{20,}"),
        "[REDACTED_OPENAI_API_KEY]",
    ),
    (
        re.compile(r"(?<![A-Za-z0-9_-])AIza[0-9A-Za-z_-]{30,}"),
        "[REDACTED_GEMINI_API_KEY]",
    ),
    (
        re.compile(r"(?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])"),
        "[REDACTED_AWS_ACCESS_KEY]",
    ),
)
_LABELED_SECRET_PATTERN = re.compile(
    r"(?i)(\b(?:[A-Z0-9_]*(?:api[_-]?key|access[_-]?token|"
    r"auth[_-]?token|password|secret)[A-Z0-9_]*|token|key)\b"
    r"\s*(?::|=)\s*[\"']?)([^\s\"'`;]{8,})"
)


def redact_text(
    text: str,
    *,
    secret_values: Iterable[str] = (),
) -> str:
    redacted = text
    for secret_value in secret_values:
        if isinstance(secret_value, str) and len(secret_value) >= 8:
            redacted = redacted.replace(secret_value, "[REDACTED]")
    for pattern, replacement in _PROVIDER_SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    redacted = _LABELED_SECRET_PATTERN.sub(
        lambda match: f"{match.group(1)}[REDACTED_SECRET]",
        redacted,
    )
    return redacted


def redact_value(
    value: Any,
    *,
    secret_values: Iterable[str] = (),
) -> Any:
    secrets = tuple(secret_values)
    if isinstance(value, str):
        return redact_text(value, secret_values=secrets)
    if isinstance(value, Mapping):
        return {
            (
                redact_text(key, secret_values=secrets)
                if isinstance(key, str)
                else key
            ): redact_value(item, secret_values=secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            redact_value(item, secret_values=secrets) for item in value
        ]
    if isinstance(value, tuple):
        return tuple(
            redact_value(item, secret_values=secrets) for item in value
        )
    return value
