"""Product search tools."""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

from api import db as database

logger = logging.getLogger(__name__)


@tool
def get_all_products() -> str:
    """Get all products from the database. Returns JSON string of product list."""
    try:
        products = database.get_all_products()
        # Clean up for LLM consumption
        cleaned = []
        for p in products:
            cleaned.append(
                {
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "category": p.get("category"),
                    "color": p.get("color"),
                    "price": float(p.get("price", 0)),
                    "quantity": int(p.get("quantity", 0)),
                    "description": p.get("description", ""),
                    "image_path": p.get("image_path", ""),
                    "is_wearable": bool(p.get("is_wearable", 0)),
                }
            )
        return json.dumps({"products": cleaned, "count": len(cleaned)})
    except Exception:
        logger.exception("get_all_products failed")
        raise


@tool
def search_products(
    query: str = "",
    limit: int = 8,
    max_price: float | None = None,
    color: str | None = None,
    category: str | None = None,
) -> str:
    """Search products with optional filters. All params optional — empty query returns all in-stock products, then filters apply.

    Examples:
    - "red shirt" → query="red shirt"
    - "under 2000" → max_price=2000  (no query needed)
    - "red shirt under 2000" → query="red shirt", max_price=2000
    """
    try:
        results = database.search_products(query, limit=limit)

        # Apply extra filters the database function doesn't handle
        if max_price is not None:
            results = [p for p in results if float(p.get("price", 0)) <= max_price]
        if color:
            results = [
                p for p in results if color.lower() in str(p.get("color", "")).lower()
            ]
        if category:
            results = [
                p
                for p in results
                if category.lower() in str(p.get("category", "")).lower()
            ]

        cleaned = []
        for p in results[:limit]:
            cleaned.append(
                {
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "category": p.get("category"),
                    "color": p.get("color"),
                    "price": float(p.get("price", 0)),
                    "quantity": int(p.get("quantity", 0)),
                    "description": p.get("description", "")[:100],
                    "image_path": p.get("image_path", ""),
                    "is_wearable": bool(p.get("is_wearable", 0)),
                }
            )

        return json.dumps({"products": cleaned, "query": query, "count": len(cleaned)})
    except Exception:
        logger.exception("search_products failed")
        raise


@tool
def get_product_by_id(product_id: int) -> str:
    """Get detailed info for a specific product by ID."""
    try:
        p = database.get_product_by_id(product_id)
        if not p:
            return json.dumps({"error": f"Product {product_id} not found"})
        return json.dumps(
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "category": p.get("category"),
                "color": p.get("color"),
                "price": float(p.get("price", 0)),
                "quantity": int(p.get("quantity", 0)),
                "description": p.get("description", ""),
                "image_path": p.get("image_path", ""),
                "is_wearable": bool(p.get("is_wearable", 0)),
            }
        )
    except Exception:
        logger.exception("get_product_by_id failed")
        raise


@tool
def get_products_by_ids(product_ids: list[int]) -> str:
    """Fetch full DB records for a list of product IDs. Use this when the planner
    already picked specific products from the catalog. Returns {products: [...]}."""
    try:
        products = []
        missing = []
        for pid in product_ids:
            p = database.get_product_by_id(int(pid))
            if not p:
                missing.append(int(pid))
                continue
            products.append(
                {
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "category": p.get("category"),
                    "color": p.get("color"),
                    "price": float(p.get("price", 0)),
                    "quantity": int(p.get("quantity", 0)),
                    "description": p.get("description", ""),
                    "image_path": p.get("image_path", ""),
                    "is_wearable": bool(p.get("is_wearable", 0)),
                }
            )
        return json.dumps(
            {"products": products, "count": len(products), "missing": missing}
        )
    except Exception:
        logger.exception("get_products_by_ids failed")
        raise


@tool
def get_products_by_category(category: str) -> str:
    """Get all products in a specific category."""
    try:
        all_products = database.get_all_products()
        products = [
            p
            for p in all_products
            if category.lower() in str(p.get("category", "")).lower()
        ]
        cleaned = []
        for p in products:
            cleaned.append(
                {
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "color": p.get("color"),
                    "price": float(p.get("price", 0)),
                    "quantity": int(p.get("quantity", 0)),
                    "image_path": p.get("image_path", ""),
                    "is_wearable": bool(p.get("is_wearable", 0)),
                }
            )
        return json.dumps(
            {"products": cleaned, "category": category, "count": len(cleaned)}
        )
    except Exception:
        logger.exception("get_products_by_category failed")
        raise
