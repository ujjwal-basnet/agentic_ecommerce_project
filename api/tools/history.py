"""Conversation history tools."""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

from api import db as database

logger = logging.getLogger(__name__)


@tool
def get_user_history(session_id: str, limit: int = 6) -> str:
    """Get recent conversation history for a user session."""
    try:
        history = database.load_history(session_id, limit=limit)
        # Return just the essential info
        simplified = []
        for h in history:
            simplified.append(
                {
                    "role": h.get("role"),
                    "content": h.get("content", "")[:200],  # Truncate long messages
                    "timestamp": h.get("timestamp"),
                }
            )
        return json.dumps({"history": simplified, "session_id": session_id})
    except Exception:
        logger.exception("get_user_history failed")
        raise
