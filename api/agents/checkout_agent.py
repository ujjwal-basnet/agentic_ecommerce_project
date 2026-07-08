"""CheckoutAgent wrapping existing checkout/order logic."""

from __future__ import annotations

import asyncio

from api.db.orders import place_order


async def checkout_impl(params: dict) -> dict:
    """Place an order from the current cart.

    Params:
        session_id (str): User session identifier.

    Returns:
        dict with keys: success (bool), order_ids (list[int]), message (str).
    """
    session_id = params.get("session_id", "")

    if not session_id:
        return {
            "success": False,
            "order_ids": [],
            "message": "Session ID is required for checkout.",
        }

    order_ids = await asyncio.to_thread(place_order, session_id)

    if not order_ids:
        return {
            "success": False,
            "order_ids": [],
            "message": "Your cart is empty. Add items before checking out.",
        }

    return {
        "success": True,
        "order_ids": order_ids,
        "message": f"Order placed successfully! {len(order_ids)} item(s) ordered.",
    }
