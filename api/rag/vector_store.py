"""Pinecone vector store with INTEGRATED embedding (llama-text-embed-v2, 1024-d).

Pinecone hosts the embedding model inside the index (field_map={"text": "text"}),
so we use `upsert_records` / `search_records` rather than raw vectors. This
saves us an embedding round-trip per query.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pinecone import Pinecone

from api import config

logger = logging.getLogger(__name__)

_pinecone_client: Pinecone | None = None
_pinecone_index: Any = None


def get_pinecone_index():
    """Return a cached reference to the Pinecone index."""
    global _pinecone_client, _pinecone_index

    if _pinecone_index is not None:
        return _pinecone_index

    if not config.PINECONE_API_KEY:
        raise RuntimeError("PINECONE_API_KEY is missing — set it in .env")

    _pinecone_client = Pinecone(api_key=config.PINECONE_API_KEY)
    _pinecone_index = _pinecone_client.Index(config.PINECONE_INDEX_NAME)
    return _pinecone_index


def _product_text(product: dict) -> str:
    """Build the text blob that Pinecone will embed for a product.

    Combine name, category, color, description, and tags so vector search
    can match on any of them. Keep it under ~500 words to stay within the
    model's truncate limit.
    """
    parts = [
        str(product.get("name") or ""),
        str(product.get("category") or ""),
        str(product.get("color") or ""),
        str(product.get("description") or ""),
        str(product.get("tags") or ""),
    ]
    return " ".join(p.strip() for p in parts if p and p.strip())


def _product_metadata(product: dict) -> dict:
    """Pinecone metadata (filterable). Must be scalar types."""
    pid = product.get("id") or product.get("product_id")
    return {
        "product_id": int(pid) if pid is not None else 0,
        "name": str(product.get("name") or ""),
        "category": str(product.get("category") or "").lower(),
        "color": str(product.get("color") or "").lower(),
        "price": float(product.get("price") or 0),
        "quantity": int(product.get("quantity") or 0),
    }


def _upsert_sync(products: list[dict]) -> int:
    """Sync upsert using Pinecone's integrated embedding endpoint.

    Returns number of records upserted.
    """
    index = get_pinecone_index()

    records: list[dict] = []
    for p in products:
        pid = p.get("id") or p.get("product_id")
        if pid is None:
            continue
        text = _product_text(p)
        if not text:
            continue
        record = {
            "_id": str(pid),
            "text": text,  # matches field_map={"text": "text"}
            **_product_metadata(p),
        }
        records.append(record)

    if not records:
        return 0

    # Pinecone integrated embedding: use upsert_records, not upsert.
    batch_size = 96  # Pinecone integrated upsert limit
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        index.upsert_records(namespace=config.PINECONE_NAMESPACE, records=batch)
        logger.info("Pinecone upsert_records batch: %d records", len(batch))

    return len(records)


async def upsert_products(products: list[dict]) -> int:
    """Embed products via Pinecone integrated embedding and upsert."""
    if not products:
        return 0
    return await asyncio.to_thread(_upsert_sync, products)


def _build_filter(filters: dict | None) -> dict | None:
    """Convert user filters to Pinecone metadata filter syntax."""
    if not filters:
        return None
    conds: list[dict] = []
    if filters.get("category"):
        conds.append({"category": {"$eq": str(filters["category"]).lower()}})
    if filters.get("max_price") is not None:
        conds.append({"price": {"$lte": float(filters["max_price"])}})
    if filters.get("min_price") is not None:
        conds.append({"price": {"$gte": float(filters["min_price"])}})
    if filters.get("color"):
        conds.append({"color": {"$eq": str(filters["color"]).lower()}})
    if not conds:
        return None
    return conds[0] if len(conds) == 1 else {"$and": conds}


def _search_sync(query: str, top_k: int, filters: dict | None) -> list[dict]:
    """Sync search using Pinecone integrated embedding."""
    index = get_pinecone_index()

    kwargs: dict[str, Any] = {
        "namespace": config.PINECONE_NAMESPACE,
        "top_k": top_k,
        "inputs": {"text": query},
        "fields": ["product_id", "name", "category", "color", "price", "quantity"],
    }
    pc_filter = _build_filter(filters)
    if pc_filter:
        kwargs["filter"] = pc_filter

    result = index.search_records(**kwargs)

    hits = result.get("result", {}).get("hits", []) if isinstance(result, dict) else []
    # SDK sometimes returns objects; normalize
    if not hits and hasattr(result, "result"):
        hits = getattr(result.result, "hits", []) or []

    output: list[dict] = []
    for hit in hits:
        if hasattr(hit, "model_dump"):
            hit = hit.model_dump()
        if isinstance(hit, dict):
            fields = hit.get("fields", {}) or {}
            score = hit.get("_score") or hit.get("score") or 0.0
            hit_id = hit.get("_id") or hit.get("id")
        else:
            fields = getattr(hit, "fields", {}) or {}
            score = getattr(hit, "score", 0.0)
            hit_id = getattr(hit, "id", None)
        output.append({
            "product_id": int(fields.get("product_id") or (hit_id or 0)),
            "name": fields.get("name", ""),
            "category": fields.get("category", ""),
            "color": fields.get("color", ""),
            "price": float(fields.get("price") or 0),
            "quantity": int(fields.get("quantity") or 0),
            "score": float(score),
            "retrieval_method": "vector_pinecone",
        })
    return output


async def search_vectors(
    query: str,
    top_k: int = 20,
    filters: dict | None = None,
) -> list[dict]:
    """Semantic search via Pinecone integrated embedding."""
    if not query or not query.strip():
        return []
    return await asyncio.to_thread(_search_sync, query, top_k, filters)


def get_index_stats() -> dict:
    """Lightweight health check. Returns total vector count."""
    try:
        index = get_pinecone_index()
        stats = index.describe_index_stats()
        if hasattr(stats, "model_dump"):
            stats = stats.model_dump()
        return {"ok": True, "stats": stats}
    except Exception as e:
        return {"ok": False, "error": str(e)}
