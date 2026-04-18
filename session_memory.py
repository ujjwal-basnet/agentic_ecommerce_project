"""Simple conversation history context backed by database chat history."""

from __future__ import annotations

MAX_HISTORY = 8


def init_memory_store() -> None:
    """Kept for app startup compatibility."""
    return None


def update_from_message(session_id: str, message: str) -> None:
    """No extraction. Chat messages are saved through database history."""
    return None


def get_context_string(
    session_id: str,
    include_db_history: bool = True,
    limit: int = MAX_HISTORY,
) -> str:
    """Get formatted recent conversation for LLM context."""
    if not include_db_history:
        return ""

    from database import load_history

    rows = load_history(session_id, limit=limit)
    if not rows:
        return ""

    lines = []
    for msg in rows:
        role = "User" if msg.get("role") == "user" else "Assistant"
        content = (msg.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content[:200]}")

    return "\n".join(lines)


def clear_memory(session_id: str) -> None:
    """Real clearing happens in database.clear_history()."""
    return None
