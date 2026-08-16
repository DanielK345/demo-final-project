"""Secret redaction shared by AI-log capture and submission paths."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

REDACTED = "[REDACTED_SECRET]"

_SENSITIVE_KEYS = re.compile(
    r"(?i)^(?:authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"client[_-]?secret|webhook[_-]?secret|password)$"
)
_SENSITIVE_ENV_KEYS = re.compile(
    r"^[A-Z][A-Z0-9_]*(?:API_KEY|ACCESS_TOKEN|REFRESH_TOKEN|CLIENT_SECRET|"
    r"WEBHOOK_SECRET|PASSWORD)$"
)
_VALUE_PATTERNS = (
    re.compile(r"sk-or-v1-[A-Za-z0-9_-]{12,}"),
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{16,}"),
    re.compile(r"\bgh[opusr]_[A-Za-z0-9]{20,}"),
)
_ASSIGNMENT = re.compile(
    r"(?i)\b("
    r"[A-Z][A-Z0-9_]*(?:API_KEY|ACCESS_TOKEN|REFRESH_TOKEN|CLIENT_SECRET|"
    r"WEBHOOK_SECRET|PASSWORD)|api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"client[_-]?secret|webhook[_-]?secret|password"
    r")(\s*[:=]\s*[\"']?)([^\s,\"']{8,})"
)


def redact_text(value: str) -> str:
    """Redact credential-shaped values while preserving surrounding context."""
    redacted = value
    for pattern in _VALUE_PATTERNS:
        redacted = pattern.sub(REDACTED, redacted)
    redacted = _ASSIGNMENT.sub(lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}", redacted)
    return redacted


def redact_secrets(value: Any) -> Any:
    """Return a JSON-compatible copy with nested secret values redacted."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        sanitized: dict[Any, Any] = {}
        for key, nested in value.items():
            key_text = str(key)
            if (_SENSITIVE_KEYS.fullmatch(key_text) or _SENSITIVE_ENV_KEYS.fullmatch(key_text)) and nested not in (
                None,
                "",
            ):
                sanitized[key] = REDACTED
            else:
                sanitized[key] = redact_secrets(nested)
        return sanitized
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [redact_secrets(item) for item in value]
    return value
