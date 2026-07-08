"""CartAgent — dispatch on action. Returns a UI component hint per action."""

from __future__ import annotations

import asyncio
import logging

from api.db import products as db_products
from api.db.cart import (
    cart_totals,
    db_add_to_cart,
    db_clear_cart,
    db_get_cart,
    db_remove_from_cart,
)

logger = logging.getLogger(__name__)


def _normalize_cart_items(cart: list[dict]) -> list[dict]:
    """Ensure each cart row has the fields CartDrawer expects."""
    items = []
    for row in cart:
        items.append({
            "id": row.get("id"),
            "product_id": row.get("product_id"),
            "product_name": row.get("product_name", ""),
            "price": float(row.get("price") or 0),
            "quantity": int(row.get("quantity") or 0),
            "image_path": row.get("image_path") or "",
            "color": row.get("color") or "",
            "category": row.get("category") or "",
        })
    return items


def _resolve_product_for_add(
    session_id: str,
    product_id: int | None,
    product_name: str,
    price: float | None,
) -> tuple[int | None, str, float]:
    """Fill in missing fields by looking up the product from Postgres.

    Planner usually gives us product_id; sometimes it gives only a name. In
    both cases we want the canonical name + current price so cart rows stay
    consistent with the catalog.
    """
    if product_id:
        record = db_products.get_product_by_id(int(product_id))
        if record:
            return (
                int(record["id"]),
                str(record.get("name") or product_name or ""),
                float(record.get("price") or price or 0),
            )

    if product_name:
        # Substring lookup so "sprite" matches "Sprite Lemon & Lime Flavoured"
        record = db_products.get_product_by_name(product_name)
        if record:
            return (
                int(record["id"]),
                str(record.get("name") or product_name),
                float(record.get("price") or price or 0),
            )

    return (product_id, product_name, float(price or 0))


async def cart_impl(params: dict) -> dict:
    """Handle add / remove / view / clear."""
    action = (params.get("action") or "view").lower()
    session_id = params.get("session_id", "")

    if action == "add":
        pid = params.get("product_id")
        name = params.get("product_name", "")
        price = params.get("price")
        quantity = int(params.get("quantity") or 1)

        resolved_id, resolved_name, resolved_price = await asyncio.to_thread(
            _resolve_product_for_add, session_id, pid, name, price
        )

        if not resolved_name:
            return {
                "action": "add",
                "success": False,
                "component": "CartConfirmation",
                "message": "I couldn't identify that product. Could you be more specific?",
            }

        await asyncio.to_thread(
            db_add_to_cart,
            session_id,
            resolved_name,
            resolved_price,
            quantity,
            resolved_id,
        )
        cart = await asyncio.to_thread(db_get_cart, session_id)
        count, total = cart_totals(cart)
        return {
            "action": "add",
            "success": True,
            "component": "CartConfirmation",
            "message": f"Added {resolved_name} to cart.",
            "items": _normalize_cart_items(cart),
            "count": count,
            "total": total,
        }

    if action == "remove":
        pid = params.get("product_id")
        name = params.get("product_name", "")
        if pid and not name:
            rec = await asyncio.to_thread(db_products.get_product_by_id, int(pid))
            if rec:
                name = rec.get("name") or ""
        await asyncio.to_thread(db_remove_from_cart, session_id, name)
        cart = await asyncio.to_thread(db_get_cart, session_id)
        count, total = cart_totals(cart)
        return {
            "action": "remove",
            "success": True,
            "component": "CartConfirmation",
            "message": f"Removed {name} from cart." if name else "Cart updated.",
            "items": _normalize_cart_items(cart),
            "count": count,
            "total": total,
        }

    if action == "clear":
        await asyncio.to_thread(db_clear_cart, session_id)
        return {
            "action": "clear",
            "success": True,
            "component": "CartDrawer",
            "message": "Cart cleared.",
            "items": [],
            "count": 0,
            "total": 0.0,
        }

    # default: view
    cart = await asyncio.to_thread(db_get_cart, session_id)
    items = _normalize_cart_items(cart)
    count, total = cart_totals(cart)
    return {
        "action": "view",
        "success": True,
        "component": "CartDrawer",
        "items": items,
        "count": count,
        "total": total,
    }
