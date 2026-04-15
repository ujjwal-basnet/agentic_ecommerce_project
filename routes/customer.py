"""Customer-facing API routes — chat SSE, cart direct, upload photo."""

from __future__ import annotations
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form
from sse_starlette.sse import EventSourceResponse

import database
import session_memory
from log import log_user_input, log_sse, log_direct_cart, log_event, log_render

from channels.capabilities import WEB_APP, CHANNELS, get_renderer_mode

router = APIRouter()


@router.get("/api/health")
async def health():
    return {"status": "ok"}


@router.post("/chat/stream")
async def chat_stream(
    message: str = Form(),
    session_id: str = Form(),
    user_image_path: str | None = Form(None),
    interface_mode: str = Form("web"),
):
    trace_id = str(uuid.uuid4())

    async def event_generator():
        try:
            from orchestrator import classify_intent, build_plan, rewrite_query
            from executor import execute_plan
            from renderer import make_sse_events

            database.ensure_session(session_id)
            session_memory.update_from_message(session_id, message)
            log_user_input(session_id, message)

            user_context = session_memory.get_context_string(session_id)
            intent = classify_intent(message, user_context)

            if not intent or intent == "chitchat":
                text = _chitchat_reply(message, session_id)
                log_event("chitchat_response", session_id=session_id, intent=intent, response=text[:300])
                yield {
                    "event": "message",
                    "data": json.dumps({"type": "text", "content": text}),
                }
                yield {
                    "event": "message",
                    "data": json.dumps({
                        "type": "cart_sync",
                        "cart_count": database.cart_count(session_id),
                    }),
                }
                database.save_message(session_id, "user", message)
                database.save_message(session_id, "assistant", text)
                log_sse(session_id, "text")
                return

            # Resolve channel capabilities from interface_mode
            channel_caps = CHANNELS.get(interface_mode, WEB_APP)
            renderer_mode = get_renderer_mode(channel_caps)

            query = rewrite_query(message, user_context)
            plan = build_plan(query, intent, channel_caps=channel_caps)

            result = execute_plan(
                plan=plan,
                session_id=session_id,
                user_input=message,
                user_image_path=user_image_path,
                trace_id=trace_id,
                channel_caps=channel_caps,
            )

            log_render(session_id, result.get("tool", ""), result.get("component"))
            log_event("pipeline_complete", session_id=session_id, intent=intent,
                      tool=result.get("tool"), component=result.get("component"),
                      steps=result.get("steps"), elapsed=result.get("elapsed"),
                      text=str(result.get("text", ""))[:300])

            for evt in make_sse_events(result, intent, mode=renderer_mode):
                yield evt
                log_sse(session_id, "tool_result", result.get("component"))

        except Exception as exc:
            import traceback
            traceback.print_exc()
            log_event("chat_error", session_id=session_id, error=str(exc)[:300])
            yield {
                "event": "message",
                "data": json.dumps({"type": "text", "content": f"Something went wrong: {exc}"}),
            }

    return EventSourceResponse(event_generator())


@router.post("/upload-photo")
async def upload_photo(
    photo: UploadFile = File(...),
    session_id: str = Form(),
):
    contents = await photo.read()
    filename = photo.filename or "upload.jpg"
    ext = Path(filename).suffix or ".jpg"
    path = database.save_user_image(contents, session_id, ext)
    return {"path": path, "session_id": session_id}


@router.get("/api/cart")
async def get_cart(session_id: str):
    database.ensure_session(session_id)
    cart = database.db_get_cart(session_id)
    total = round(sum(float(i.get("price", 0)) * int(i.get("quantity", 0)) for i in cart), 2)
    count = sum(int(i.get("quantity", 0)) for i in cart)
    return {"items": cart, "count": count, "total": total}


@router.post("/api/cart/add")
async def add_to_cart_direct(
    session_id: str = Form(...),
    product_name: str = Form(...),
    price: float = Form(...),
    quantity: int = Form(1),
):
    database.ensure_session(session_id)
    database.db_add_to_cart(session_id, product_name, float(price), int(quantity))
    log_direct_cart(session_id, product_name, "add")
    cart = database.db_get_cart(session_id)
    total = round(sum(float(i.get("price", 0)) * int(i.get("quantity", 0)) for i in cart), 2)
    count = sum(int(i.get("quantity", 0)) for i in cart)
    return {
        "success": True,
        "message": f"Added {quantity} x {product_name} to cart",
        "cart_total_items": count,
        "cart_total_price": total,
    }


@router.post("/api/cart/update")
async def update_cart_item(
    session_id: str = Form(...),
    product_name: str = Form(...),
    quantity: int = Form(...),
):
    database.ensure_session(session_id)
    database.db_update_cart_quantity(session_id, product_name, quantity)
    cart = database.db_get_cart(session_id)
    total = round(sum(float(i.get("price", 0)) * int(i.get("quantity", 0)) for i in cart), 2)
    count = sum(int(i.get("quantity", 0)) for i in cart)
    return {"success": True, "cart_total_items": count, "cart_total_price": total}


@router.post("/api/cart/remove")
async def remove_from_cart(
    session_id: str = Form(...),
    product_name: str = Form(...),
):
    database.ensure_session(session_id)
    database.db_remove_from_cart(session_id, product_name)
    cart = database.db_get_cart(session_id)
    total = round(sum(float(i.get("price", 0)) * int(i.get("quantity", 0)) for i in cart), 2)
    count = sum(int(i.get("quantity", 0)) for i in cart)
    return {"success": True, "cart_total_items": count, "cart_total_price": total}


@router.post("/api/checkout")
async def checkout(session_id: str = Form(...)):
    database.ensure_session(session_id)
    cart = database.db_get_cart(session_id)
    if not cart:
        return {"success": False, "message": "Cart is empty"}
    total = round(sum(float(i.get("price", 0)) * int(i.get("quantity", 0)) for i in cart), 2)
    count = sum(int(i.get("quantity", 0)) for i in cart)
    order_ids = database.place_order(session_id)
    return {
        "success": True,
        "message": f"Order placed! {count} items totaling Rs. {total}",
        "order_ids": order_ids,
        "total": total,
        "item_count": count,
    }


@router.post("/clear-chat")
async def clear_chat(session_id: str = Form()):
    database.clear_history(session_id)
    session_memory.clear_memory(session_id)
    return {"ok": True}


def _chitchat_reply(message: str, session_id: str = "") -> str:
    try:
        from llm import call_llm
        context = ""
        if session_id:
            context = session_memory.get_context_string(session_id)
        system = (
            "You are a friendly e-commerce shopping assistant for SmartShop. "
            "Greet warmly, keep it short. You help find products, manage cart, "
            "get recommendations, and virtual try-on."
        )
        if context:
            system += f"\n\nHere is what you know about this customer:\n{context}\nUse this context to personalize your response (e.g. greet them by name if known)."
        return call_llm(system, message, temperature=0.7)
    except Exception:
        m = message.lower().strip()
        replies = {
            "hi": "Hello! What are you shopping for today?",
            "hello": "Hi there! How can I help you find something?",
            "hey": "Hey! What can I help you with?",
            "namaste": "Namaste! Welcome to SmartShop. What are you looking for?",
            "how are you": "I'm great! Ready to help you shop. What are you looking for?",
        }
        return next((v for k, v in replies.items() if k in m),
                     "Happy to help! Search for products or ask for recommendations.")
