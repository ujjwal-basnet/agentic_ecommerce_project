"""In-RAM session memory for user context. Not persistent — lives only while server runs."""

from __future__ import annotations
from collections import defaultdict
from typing import Any

_store: dict[str, dict[str, Any]] = defaultdict(lambda: {
    "name": None,
    "preferences": [],
    "recent_queries": [],
    "facts": [],
})

MAX_RECENT = 10


def get_memory(session_id: str) -> dict[str, Any]:
    return _store[session_id]


def update_from_message(session_id: str, message: str):
    """Extract and store useful context from a user message."""
    mem = _store[session_id]

    # Track recent queries
    mem["recent_queries"].append(message)
    if len(mem["recent_queries"]) > MAX_RECENT:
        mem["recent_queries"] = mem["recent_queries"][-MAX_RECENT:]

    # Try to detect name introductions
    msg_l = message.lower().strip()
    for prefix in ("my name is ", "i am ", "i'm ", "call me ", "this is "):
        if prefix in msg_l:
            idx = msg_l.index(prefix) + len(prefix)
            name_part = message[idx:].strip().split()[0].strip(".,!?")
            if name_part and len(name_part) > 1:
                mem["name"] = name_part.title()
                break

    # Detect preferences
    pref_triggers = {
        "i like ": "likes",
        "i love ": "loves",
        "i prefer ": "prefers",
        "i hate ": "dislikes",
        "i don't like ": "dislikes",
        "my favorite ": "favorite",
        "my size is ": "size",
        "my budget is ": "budget",
    }
    for trigger, label in pref_triggers.items():
        if trigger in msg_l:
            idx = msg_l.index(trigger) + len(trigger)
            value = message[idx:].strip().rstrip(".,!?")
            if value:
                mem["preferences"].append(f"{label}: {value}")
                if len(mem["preferences"]) > 20:
                    mem["preferences"] = mem["preferences"][-20:]
                break


def get_context_string(session_id: str, include_db_history: bool = True) -> str:
    """Build a context string for LLM prompts, including DB chat history."""
    mem = _store[session_id]
    parts = []
    if mem["name"]:
        parts.append(f"Customer name: {mem['name']}")
    if mem["preferences"]:
        parts.append("Preferences: " + "; ".join(mem["preferences"][-5:]))
    if mem["facts"]:
        parts.append("Known facts: " + "; ".join(mem["facts"][-5:]))

    if include_db_history:
        try:
            from database import load_history
            history = load_history(session_id, limit=10)
            if history:
                lines = []
                for h in history:
                    role = h.get("role", "user")
                    text = h.get("content", "")[:150]
                    if text:
                        lines.append(f"{role}: {text}")
                if lines:
                    parts.append("Recent conversation:\n" + "\n".join(lines))
        except Exception:
            pass

    if mem["recent_queries"]:
        parts.append("Recent user queries: " + " | ".join(mem["recent_queries"][-5:]))

    return "\n".join(parts) if parts else ""


def clear_memory(session_id: str):
    """Clear session memory."""
    if session_id in _store:
        del _store[session_id]
