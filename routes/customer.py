"""Customer-facing API routes — chat SSE, cart, upload, orders."""

from __future__ import annotations
import json
import logging
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form
from sse_starlette.sse import EventSourceResponse

import analytics_ml
import database
import engine
import session_memory
from schemas import (
    CartActionResponse,
    CartResponse,
    CheckoutResponse,
    ClearChatResponse,
    HealthResponse,
    OrdersResponse,
    UploadPhotoResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/health", response_model=HealthResponse)
async def health():
    return {"status": "ok"}


@router.post("/chat/stream")
async def chat_stream(
    message: str = Form(),
    session_id: str = Form(),
    user_image_path: str | None = Form(None),
    interface_mode: str = Form("web"),
):
    async def event_generator():
        try:
            database.ensure_session(session_id)
            channel = "web" if interface_mode == "web" else "text"

            result = await engine.run(
                message,
                channel=channel,
                session_id=session_id,
                user_image_path=user_image_path,
            )

            # Text response
            text = result.get("text", "")
            if text:
                yield {
                    "event": "message",
                    "data": json.dumps({"type": "text", "content": text}),
                }

            # UI component (web only)
            component = result.get("component")
            if component and channel == "web":
                data = result.get("data", {})
                component_data = data
                if component in {"ProductList", "RecommendGrid"}:
                    component_data = result.get("products") or data.get("products", [])
                yield {
                    "event": "message",
                    "data": json.dumps({
                        "type": "tool_result",
                        "tool": component,
                        "component": component,
                        "data": component_data,
                        "products": result.get("products") or data.get("products", []),
                    }),
                }

            # Images (e.g. virtual try-on result)
            for img_path in result.get("images") or []:
                yield {
                    "event": "message",
                    "data": json.dumps({"type": "image", "image_path": img_path}),
                }

            # Cart sync
            yield {
                "event": "message",
                "data": json.dumps({
                    "type": "cart_sync",
                    "cart_count": result.get("cart_count", 0),
                }),
            }

        except Exception as exc:
            logger.exception("chat_stream failed session=%s message=%r", session_id, message)
            yield {
                "event": "error",
                "data": json.dumps({"type": "error", "content": f"Something went wrong: {exc}"}),
            }
            raise

    return EventSourceResponse(event_generator())


@router.post("/upload-photo", response_model=UploadPhotoResponse)
async def upload_photo(
    photo: UploadFile = File(...),
    session_id: str = Form(),
):
    contents = await photo.read()
    ext = Path(photo.filename or "upload.jpg").suffix or ".jpg"
    path = database.save_user_image(contents, session_id, ext)
    return {"path": path, "session_id": session_id}


@router.get("/api/cart", response_model=CartResponse)
async def get_cart(session_id: str):
    database.ensure_session(session_id)
    cart = database.db_get_cart(session_id)
    count, total = database.cart_totals(cart)
    return {"items": cart, "count": count, "total": total}


@router.post("/api/cart/add", response_model=CartActionResponse)
async def add_to_cart_direct(
    session_id: str = Form(...),
    product_name: str = Form(...),
    price: float = Form(...),
    quantity: int = Form(1),
):
    database.ensure_session(session_id)
    database.db_add_to_cart(session_id, product_name, float(price), int(quantity))
    analytics_ml.invalidate_cache()
    cart = database.db_get_cart(session_id)
    count, total = database.cart_totals(cart)
    return {
        "success": True,
        "message": f"Added {quantity} x {product_name} to cart",
        "cart_total_items": count,
        "cart_total_price": total,
    }


@router.post("/api/cart/update", response_model=CartActionResponse)
async def update_cart_item(
    session_id: str = Form(...),
    product_name: str = Form(...),
    quantity: int = Form(...),
):
    database.ensure_session(session_id)
    database.db_update_cart_quantity(session_id, product_name, quantity)
    analytics_ml.invalidate_cache()
    cart = database.db_get_cart(session_id)
    count, total = database.cart_totals(cart)
    return {"success": True, "cart_total_items": count, "cart_total_price": total}


@router.post("/api/cart/remove", response_model=CartActionResponse)
async def remove_from_cart(
    session_id: str = Form(...),
    product_name: str = Form(...),
):
    database.ensure_session(session_id)
    database.db_remove_from_cart(session_id, product_name)
    analytics_ml.invalidate_cache()
    cart = database.db_get_cart(session_id)
    count, total = database.cart_totals(cart)
    return {"success": True, "cart_total_items": count, "cart_total_price": total}


@router.post("/api/checkout", response_model=CheckoutResponse)
async def checkout(session_id: str = Form(...)):
    database.ensure_session(session_id)
    cart = database.db_get_cart(session_id)
    if not cart:
        return {"success": False, "message": "Cart is empty", "order_ids": [], "total": 0, "item_count": 0}
    count, total = database.cart_totals(cart)
    order_ids = database.place_order(session_id)
    analytics_ml.invalidate_cache()
    return {
        "success": True,
        "message": f"Order placed! {count} items totaling Rs. {total}",
        "order_ids": order_ids,
        "total": total,
        "item_count": count,
    }


@router.get("/api/orders", response_model=OrdersResponse)
async def get_orders(session_id: str):
    database.ensure_session(session_id)
    orders = database.get_orders_by_session(session_id)
    stats = database.get_order_stats_by_session(session_id)
    return {
        "orders": orders,
        "total_orders": stats["total_orders"],
        "total_spent": round(stats["total_spent"], 2),
    }


@router.post("/clear-chat", response_model=ClearChatResponse)
async def clear_chat(session_id: str = Form()):
    database.clear_history(session_id)
    session_memory.clear_memory(session_id)
    return {"ok": True}
