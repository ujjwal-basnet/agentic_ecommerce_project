"""RecommendationAgent — dual RAG with session context, hydrated from DB."""

from __future__ import annotations

import asyncio
import logging

from api.agents.product_search import _hydrate_from_db
from api.db import products as db_products
from api.rag.fusion import reciprocal_rank_fusion
from api.rag.vector_store import search_vectors

logger = logging.getLogger(__name__)


async def recommendation_impl(params: dict) -> dict:
    """Return personalized recommendations.

    Uses session context (browsing history, preferences) as the query to
    Pinecone. Falls back to a random sample from the catalog if Pinecone
    is empty or unavailable.
    """
    context = (params.get("context") or "").strip()
    limit = int(params.get("limit") or 6)

    query = context or "popular trending products recommendations"

    # Vector path only — no structured filters for broad recommendations
    vector_results: list[dict] = []
    try:
        vector_results = await search_vectors(query=query, top_k=limit * 3)
    except Exception as e:
        logger.warning("Pinecone failed for recommendations: %s", e)

    if vector_results:
        fused = reciprocal_rank_fusion([vector_results], top_n=limit)
        ids = [int(r["product_id"]) for r in fused if r.get("product_id")]
        hydrated = await asyncio.to_thread(_hydrate_from_db, ids)
        products = []
        for result in fused:
            pid = int(result.get("product_id") or 0)
            full = hydrated.get(pid)
            if not full:
                continue
            products.append({
                "id": full.get("id"),
                "name": full.get("name"),
                "category": full.get("category"),
                "color": full.get("color"),
                "price": float(full.get("price") or 0),
                "description": full.get("description", ""),
                "image_path": full.get("image_path", ""),
                "quantity": int(full.get("quantity") or 0),
                "score": result.get("score", 0.0),
                "retrieval_method": "recommendation",
            })
        if products:
            return {"products": products, "count": len(products)}

    # Fallback: diverse sample from full catalog
    all_products = await asyncio.to_thread(db_products.get_all_products)
    sample = all_products[:limit]
    out = [
        {
            "id": p.get("id"),
            "name": p.get("name"),
            "category": p.get("category"),
            "color": p.get("color"),
            "price": float(p.get("price") or 0),
            "description": p.get("description", ""),
            "image_path": p.get("image_path", ""),
            "quantity": int(p.get("quantity") or 0),
            "score": 0.0,
            "retrieval_method": "fallback",
        }
        for p in sample
    ]
    return {"products": out, "count": len(out)}
