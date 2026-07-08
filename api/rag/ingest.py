"""Product → Pinecone ingestion.

Loads every product from Postgres and upserts it into the Pinecone index
using integrated embedding (llama-text-embed-v2). Called on server startup
and whenever a product is created/updated/deleted.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from api.db import products as db_products
from api.rag.vector_store import get_pinecone_index, upsert_products

logger = logging.getLogger(__name__)


async def ingest_all_products(force: bool = False) -> dict[str, Any]:
    """Embed and upsert every product from Postgres into Pinecone.

    Args:
        force: If True, re-ingest even if Pinecone already has records.
    """
    try:
        index = get_pinecone_index()
        stats = index.describe_index_stats()
        if hasattr(stats, "model_dump"):
            stats = stats.model_dump()
        total = int(stats.get("total_vector_count") or 0)

        all_products = await asyncio.to_thread(db_products.get_all_products)
        pg_count = len(all_products)

        if not force and total >= pg_count and total > 0:
            logger.info(
                "Pinecone already has %d vectors (Postgres has %d). Skipping ingest.",
                total, pg_count,
            )
            return {"ingested": 0, "total": total, "skipped": True}

        logger.info(
            "Ingesting %d products into Pinecone (index has %d, force=%s)",
            pg_count, total, force,
        )
        n = await upsert_products(all_products)
        logger.info("Pinecone ingest complete: upserted %d products", n)
        return {"ingested": n, "total_before": total, "skipped": False}
    except Exception as e:
        logger.exception("Pinecone ingest failed: %s", e)
        return {"ingested": 0, "error": str(e)}


async def upsert_single_product(product_id: int) -> bool:
    """Re-ingest a single product (call on update/create)."""
    try:
        product = await asyncio.to_thread(db_products.get_product_by_id, product_id)
        if not product:
            return False
        await upsert_products([product])
        return True
    except Exception as e:
        logger.warning("Single product upsert failed for id=%s: %s", product_id, e)
        return False


async def delete_product_vector(product_id: int) -> bool:
    """Remove a product vector from Pinecone (call on delete)."""
    try:
        index = get_pinecone_index()
        await asyncio.to_thread(
            index.delete,
            ids=[str(product_id)],
            namespace="__default__",
        )
        return True
    except Exception as e:
        logger.warning("Pinecone delete failed for id=%s: %s", product_id, e)
        return False
