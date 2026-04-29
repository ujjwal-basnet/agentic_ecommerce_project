"""Cart tools."""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

from api import db as database
from api.analytics import forecast as analytics_ml

logger = logging.getLogger(__name__)


@tool
def view_cart(session_id: str) -> str:
    """View the current cart for a session. Returns cart items and total."""
    try:
        cart = database.db_get_cart(session_id)
        count, total = database.cart_totals(cart)

        return json.dumps(
            {
                "items": cart,
                "count": count,
                "total": total,
                "is_empty": len(cart) == 0,
                "text": "Your cart is empty."
                if not cart
                else f"Your cart has {count} item(s), totaling Rs. {total}.",
            }
        )
    except Exception:
        logger.exception("view_cart failed")
        raise


@tool
def add_to_cart(
    session_id: str,
    product_id: int | None = None,
    product_name: str | None = None,
    quantity: int = 1,
) -> str:
    """Add a product to cart. Prefer product_id (from Catalog); product_name is a fallback."""
    try:
        prod = None
        if product_id is not None:
            prod = database.get_product_by_id(int(product_id))
        if prod is None and product_name:
            prod = database.get_product_by_name(product_name)
        if not prod:
            ref = f"id={product_id}" if product_id is not None else f"'{product_name}'"
            return json.dumps(
                {
                    "success": False,
                    "error": f"Product {ref} not found",
                    "message": f"I couldn't find that product ({ref}) in the catalog.",
                }
            )

        price = float(prod.get("price", 0))
        database.db_add_to_cart(
            session_id, prod["name"], price, quantity, product_id=prod.get("id")
        )
        analytics_ml.invalidate_cache()

        cart = database.db_get_cart(session_id)
        count, total = database.cart_totals(cart)
        message = f"Added {quantity} x {prod['name']} to your cart."

        return json.dumps(
            {
                "success": True,
                "message": message,
                "text": message,
                "added": prod["name"],
                "product_id": prod.get("id"),
                "price": price,
                "image_path": prod.get("image_path", ""),
                "quantity": quantity,
                "count": count,
                "total": total,
                "cart_count": count,
                "cart_total": total,
                "cart_total_items": count,
                "cart_total_price": total,
            }
        )
    except Exception:
        logger.exception("add_to_cart failed")
        raise


@tool
def remove_from_cart(
    session_id: str,
    product_id: int | None = None,
    product_name: str | None = None,
) -> str:
    """Remove a product from cart. Prefer product_id (from Catalog); product_name is a fallback."""
    try:
        removed_name = product_name
        if product_id is not None:
            prod = database.get_product_by_id(int(product_id))
            if prod:
                removed_name = prod["name"]

        if not removed_name:
            return json.dumps(
                {
                    "success": False,
                    "error": "No product_id or product_name provided",
                    "message": "I need to know which product to remove.",
                }
            )

        database.db_remove_from_cart(session_id, removed_name)
        analytics_ml.invalidate_cache()
        cart = database.db_get_cart(session_id)
        count, total = database.cart_totals(cart)
        message = f"Removed {removed_name} from your cart."

        return json.dumps(
            {
                "success": True,
                "message": message,
                "text": message,
                "removed": removed_name,
                "product_id": product_id,
                "count": count,
                "total": total,
                "cart_count": count,
                "cart_total": total,
                "cart_total_items": count,
                "cart_total_price": total,
            }
        )
    except Exception:
        logger.exception("remove_from_cart failed")
        raise


@tool
def clear_cart(session_id: str) -> str:
    """Clear all items from cart."""
    try:
        database.db_clear_cart(session_id)
        return json.dumps(
            {
                "success": True,
                "message": "Cart cleared.",
                "text": "Cart cleared.",
                "count": 0,
                "total": 0,
                "cart_count": 0,
                "cart_total": 0,
                "cart_total_items": 0,
                "cart_total_price": 0,
            }
        )
    except Exception:
        logger.exception("clear_cart failed")
        raise
