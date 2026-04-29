"""Input sanitizer for prompt-injection attempts.

Detects common patterns where the user tries to override the system prompt or
extract internal instructions. Strips matches and returns a SanitizeResult so the
caller can decide whether to log, refuse, or proceed.

Intentionally conservative: false positives degrade UX; false negatives can leak
the system prompt or hijack tool calls. Pair with output moderation for defense
in depth.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Patterns are case-insensitive. Order roughly by severity.
_INJECTION_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        "ignore_previous",
        r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?|messages?)",
    ),
    (
        "disregard_previous",
        r"(disregard|forget|override|bypass)\s+(all\s+)?(previous|prior|above|earlier|system)\s+(instructions?|prompts?|rules?)",
    ),
    (
        "reveal_system",
        r"(reveal|show|print|repeat|output|expose|leak)\s+(your|the)\s+(system\s+)?(prompt|instructions?|rules?|guidelines?)",
    ),
    (
        "act_as",
        r"\b(act|behave|pretend|roleplay|respond)\s+as\s+(if\s+you\s+(are|were)|a|an)\b",
    ),
    ("you_are_now", r"\byou\s+are\s+(now|from\s+now\s+on)\b"),
    ("new_role", r"\bnew\s+(role|task|instructions?|system\s+prompt)\b"),
    (
        "dan_jailbreak",
        r"\b(do\s+anything\s+now|DAN\s+mode|developer\s+mode\s+enabled)\b",
    ),
    ("system_tag", r"<\s*/?\s*(system|sys|instructions?)\s*>"),
    ("end_of_prompt", r"###\s*(end|stop|new)\s+(of\s+)?(prompt|instructions?|system)"),
    ("shell_meta", r"`{3,}|\$\(\s*[a-z_/]+|sudo\s+(apt-get|rm|chmod)"),
)

_COMPILED = tuple(
    (name, re.compile(pat, re.IGNORECASE)) for name, pat in _INJECTION_PATTERNS
)

MAX_INPUT_CHARS = 4000


@dataclass
class SanitizeResult:
    cleaned: str
    flagged: bool
    matches: list[str] = field(default_factory=list)
    truncated: bool = False

    @property
    def safe(self) -> bool:
        return not self.flagged


def sanitize_user_input(text: str) -> SanitizeResult:
    """Strip injection patterns; flag if any match. Truncate over-long input."""
    if not text:
        return SanitizeResult(cleaned="", flagged=False)

    truncated = len(text) > MAX_INPUT_CHARS
    cleaned = text[:MAX_INPUT_CHARS] if truncated else text

    matches: list[str] = []
    for name, pat in _COMPILED:
        if pat.search(cleaned):
            matches.append(name)
            cleaned = pat.sub("[redacted]", cleaned)

    return SanitizeResult(
        cleaned=cleaned.strip(),
        flagged=bool(matches),
        matches=matches,
        truncated=truncated,
    )
