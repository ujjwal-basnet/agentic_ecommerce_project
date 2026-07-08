"""ResolveProductsAgent — zero-RAG lookup by explicit product IDs.

The catalog-aware planner already knows which products match the user's
request, so it can emit ID lists directly. This agent just fetches those
full records from Postgres. No vector search, no fuzzy matching.
"""

from __future__ import annotations

import asyncio
import logging

from api.db import products as db_products

logger = logging.getLogger(__name__)


async def resolve_products_impl(params: dict) -> dict:
    """Fetch full product records for a list of IDs.

    Params:
        product_ids: list[int] — IDs to fetch (duplicates are deduped, unknown IDs dropped)

    Returns:
        { products: list[dict], count: int }
    """
    raw_ids = params.get("product_ids") or params.get("ids") or []
    ids: list[int] = []
    for pid in raw_ids:
        try:
            ids.append(int(pid))
        except (TypeError, ValueError):
            continue

    if not ids:
        logger.info("resolve_products: no valid IDs provided")
        return {"products": [], "count": 0, "component": "ProductList"}

    # Preserve order requested by the planner
    ordered_ids: list[int] = []
    seen: set[int] = set()
    for pid in ids:
        if pid in seen:
            continue
        seen.add(pid)
        ordered_ids.append(pid)

    records = await asyncio.to_thread(db_products.get_products_by_ids, ordered_ids)
    by_id = {int(p.get("id")): p for p in records if p.get("id") is not None}

    products: list[dict] = []
    for pid in ordered_ids:
        row = by_id.get(pid)
        if not row:
            continue
        products.append({
            "id": row.get("id"),
            "name": row.get("name"),
            "category": row.get("category"),
            "color": row.get("color"),
            "price": float(row.get("price") or 0),
            "description": row.get("description", ""),
            "image_path": row.get("image_path", ""),
            "quantity": int(row.get("quantity") or 0),
            "is_wearable": bool(row.get("is_wearable")),
            "retrieval_method": "resolve",
        })

    logger.info(
        "resolve_products: requested=%d found=%d",
        len(ordered_ids),
        len(products),
    )
    return {
        "products": products,
        "count": len(products),
        "component": "ProductList",
    }
