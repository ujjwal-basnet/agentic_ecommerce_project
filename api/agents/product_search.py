"""ProductSearchAgent — dual RAG (Pinecone vector + Postgres structured + RRF)."""

from __future__ import annotations

import asyncio
import logging

from api.db import products as db_products
from api.rag.fusion import reciprocal_rank_fusion
from api.rag.structured import search_structured
from api.rag.vector_store import search_vectors

logger = logging.getLogger(__name__)


def _hydrate_from_db(ids: list[int]) -> dict[int, dict]:
    """Fetch full product records for the given IDs from Postgres cache."""
    if not ids:
        return {}
    products = db_products.get_products_by_ids(ids)
    return {int(p["id"]): p for p in products if p.get("id") is not None}


async def product_search_impl(params: dict) -> dict:
    """Search products using dual RAG, then hydrate with full Postgres records."""
    query = (params.get("query") or "").strip()
    max_price = params.get("max_price")
    min_price = params.get("min_price")
    category = params.get("category")
    color = params.get("color")
    limit = int(params.get("limit") or 8)

    # Filters shared across vector + structured paths
    filters: dict = {}
    if category:
        filters["category"] = category
    if max_price is not None:
        filters["max_price"] = max_price
    if min_price is not None:
        filters["min_price"] = min_price
    if color:
        filters["color"] = color

    async def _vector_path() -> list[dict]:
        if not query:
            # No text query — let structured path handle it. Pinecone requires a query.
            return []
        try:
            return await search_vectors(
                query=query,
                top_k=limit * 3,
                filters=filters if filters else None,
            )
        except Exception as e:
            logger.warning("Pinecone search failed: %s", e)
            return []

    async def _structured_path() -> list[dict]:
        try:
            return await search_structured(
                query=query or None,
                max_price=max_price,
                min_price=min_price,
                category=category,
                color=color,
                limit=limit * 3,
            )
        except Exception as e:
            logger.warning("Structured search failed: %s", e)
            return []

    vector_results, structured_results = await asyncio.gather(
        _vector_path(), _structured_path()
    )
    vector_results = [r for r in vector_results if float(r.get("score") or 0) >= 0.18]

    # Fuse with RRF
    lists = [lst for lst in (vector_results, structured_results) if lst]
    fused = reciprocal_rank_fusion(lists, top_n=limit) if lists else []

    # Hydrate with full product records from Postgres (names, images, desc, price)
    ids = [int(r["product_id"]) for r in fused if r.get("product_id")]
    hydrated_map = await asyncio.to_thread(_hydrate_from_db, ids)

    products: list[dict] = []
    for result in fused:
        pid = int(result.get("product_id") or 0)
        full = hydrated_map.get(pid)
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
            "is_wearable": bool(full.get("is_wearable")),
            "score": result.get("score", 0.0),
            "retrieval_method": result.get("retrieval_method", "fused"),
        })

    logger.info(
        "product_search: query=%r filters=%s vector=%d structured=%d returned=%d",
        query, filters, len(vector_results), len(structured_results), len(products),
    )
    return {"products": products, "count": len(products)}
