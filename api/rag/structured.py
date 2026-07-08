"""PostgreSQL structured search path for dual RAG.

Lenient filters: category and color use ILIKE substring match so the LLM can
emit 'shirt' and we still match 'shirts' or 'Men Shirt'. Pinecone handles
semantic relevance; this path is the exact-filter safety net.
"""

from __future__ import annotations

import asyncio
import re

from api.db.pool import get_conn

STOP_WORDS = {
    "a", "an", "and", "any", "are", "can", "could", "do", "does", "for", "have",
    "how", "i", "is", "it", "me", "my", "of", "price", "product", "products",
    "rate", "rs", "show", "the", "this", "to", "what", "you",
}


def _tokenize(text: str) -> list[str]:
    tokens = [re.sub(r"[^a-z0-9]", "", t.lower()) for t in text.split() if t.strip()]
    return [t for t in tokens if len(t) > 1 and t not in STOP_WORDS]


def _build_and_execute(
    query: str | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
    category: str | None = None,
    color: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Build and run the SQL query. Returns raw row dicts."""
    conn = get_conn()

    conditions: list[str] = ["quantity > 0"]
    params: list = []

    if max_price is not None:
        conditions.append("price <= ?")
        params.append(max_price)

    if min_price is not None:
        conditions.append("price >= ?")
        params.append(min_price)

    if category:
        # Lenient: substring match so 'shirt' matches 'Shirts', 'Men Shirt', etc.
        conditions.append("LOWER(category) LIKE ?")
        params.append(f"%{category.lower()}%")

    if color:
        conditions.append("LOWER(color) LIKE ?")
        params.append(f"%{color.lower()}%")

    where_clause = " AND ".join(conditions)

    tokens = _tokenize(query) if query else []

    if tokens:
        tsquery_str = " | ".join(tokens)
        doc_expr = (
            "to_tsvector('simple', COALESCE(name,'') || ' ' || "
            "COALESCE(category,'') || ' ' || COALESCE(color,'') || ' ' || "
            "COALESCE(description,'') || ' ' || COALESCE(tags,''))"
        )
        sql = (
            f"SELECT *, "
            f"ts_rank({doc_expr}, to_tsquery('simple', ?)) AS _rank "
            f"FROM products WHERE {where_clause} "
            f"AND {doc_expr} @@ to_tsquery('simple', ?) "
            f"ORDER BY _rank DESC, id LIMIT ?"
        )
        params = [tsquery_str] + params + [tsquery_str, limit]
    else:
        sql = (
            f"SELECT *, 0.0::float AS _rank "
            f"FROM products WHERE {where_clause} "
            f"ORDER BY id LIMIT ?"
        )
        params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


async def search_structured(
    query: str | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
    category: str | None = None,
    color: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Postgres structured search. Returns SearchResult-shaped dicts."""
    rows = await asyncio.to_thread(
        _build_and_execute, query, max_price, min_price, category, color, limit
    )

    results: list[dict] = []
    for row in rows:
        results.append({
            "product_id": row.get("id"),
            "name": row.get("name", ""),
            "price": float(row.get("price", 0) or 0),
            "category": row.get("category", ""),
            "color": row.get("color"),
            "description": row.get("description", ""),
            "image_path": row.get("image_path"),
            "quantity": int(row.get("quantity", 0) or 0),
            "score": float(row.get("_rank") or 0.0),
            "retrieval_method": "structured_postgres",
        })
    return results
