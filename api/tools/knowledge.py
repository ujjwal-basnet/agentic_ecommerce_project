"""Knowledge-base tools."""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

from api import db as database

logger = logging.getLogger(__name__)


@tool
def search_knowledge_base(query: str) -> str:
    """Search store policies, FAQs, and information (returns, shipping, sizing, payment, warranty, privacy)."""
    try:
        results = database.search_knowledge_base(query, limit=3)
        if not results:
            return json.dumps(
                {"found": False, "message": "No matching FAQ or policy found."}
            )
        entries = []
        for r in results:
            entries.append(
                {
                    "title": r["title"],
                    "category": r["category"],
                    "content": r["content"],
                }
            )
        return json.dumps({"found": True, "entries": entries})
    except Exception:
        logger.exception("search_knowledge_base failed")
        raise
