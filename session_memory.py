"""Simple conversation history context backed by database chat history."""

from __future__ import annotations

MAX_HISTORY = 6  # 3 user + 3 assistant turns


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
    """Last 3 user + last 3 assistant messages, chronological."""
    if not include_db_history:
        return ""

    from database import load_history

    per_role = max(1, limit // 2)
    rows = load_history(session_id, limit=max(limit * 4, 24))
    if not rows:
        return ""

    users = [m for m in rows if m.get("role") == "user"][-per_role:]
    assistants = [m for m in rows if m.get("role") == "assistant"][-per_role:]
    keep = {id(m) for m in users} | {id(m) for m in assistants}
    ordered = [m for m in rows if id(m) in keep]

    lines = []
    for msg in ordered:
        role = "User" if msg.get("role") == "user" else "Assistant"
        content = (msg.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content[:200]}")

    return "\n".join(lines)


def clear_memory(session_id: str) -> None:
    """Real clearing happens in database.clear_history()."""
    return None
