"""KnowledgeBaseAgent wrapping existing knowledge base search."""

from __future__ import annotations

import asyncio

from api.db.knowledge import search_knowledge_base


async def knowledge_base_impl(params: dict) -> dict:
    """Search the knowledge base for FAQ/policy answers.

    Params:
        query (str): The question or topic to search for.
        limit (int, default 3): Maximum number of results.

    Returns:
        dict with keys: results (list[dict]), count (int).
    """
    query = params.get("query", "")
    limit = params.get("limit", 3)

    results = await asyncio.to_thread(search_knowledge_base, query, limit)

    return {
        "results": results,
        "count": len(results),
    }
