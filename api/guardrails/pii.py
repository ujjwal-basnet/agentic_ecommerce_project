"""Output guardrails for model text before it is returned to users."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?977[-\s]?)?(?:98\d{8}|97\d{8})(?!\d)")


@dataclass
class OutputFilterResult:
    text: str
    flagged: bool
    matches: list[str] = field(default_factory=list)


def filter_model_output(text: str) -> OutputFilterResult:
    """Redact obvious email/phone PII from generated text."""
    matches: list[str] = []
    cleaned = text or ""
    if _EMAIL_RE.search(cleaned):
        matches.append("email")
        cleaned = _EMAIL_RE.sub("[redacted-email]", cleaned)
    if _PHONE_RE.search(cleaned):
        matches.append("phone")
        cleaned = _PHONE_RE.sub("[redacted-phone]", cleaned)
    return OutputFilterResult(text=cleaned, flagged=bool(matches), matches=matches)
