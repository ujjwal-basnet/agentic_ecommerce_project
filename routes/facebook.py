"""Facebook Messenger webhook handler.

Routes incoming Messenger messages through the orchestrator
and formats responses using Messenger's Generic Templates and Buttons.

Setup:
1. Create Facebook App at developers.facebook.com
2. Add Messenger product, get Page Access Token
3. Set FB_PAGE_ACCESS_TOKEN and FB_VERIFY_TOKEN in .env
4. Configure webhook: https://your-domain.com/api/facebook/webhook
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

import config
import database
from channels.capabilities import FB_MESSENGER
from log import log_event, log_user_input

router = APIRouter(prefix="/api/facebook")
_log = logging.getLogger("smartshop.facebook")


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = "",
    hub_verify_token: str = "",
    hub_challenge: str = "",
):
    """Verify webhook with Facebook.
    
    Facebook sends a GET request to verify the webhook endpoint.
    We must return the challenge if the verify token matches.
    """
    expected_token = getattr(config, 'FB_VERIFY_TOKEN', 'smartshop-webhook')
    
    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        _log.info("Facebook webhook verified")
        return Response(content=hub_challenge, media_type="text/plain")
    
    _log.warning("Facebook webhook verification failed")
    return Response(content="Verification failed", status_code=403)


@router.post("/webhook")
async def receive_message(request: Request):
    """Receive and process incoming Facebook Messenger messages."""
    try:
        body = await request.json()
        _log.debug("Received Facebook payload: %s", json.dumps(body)[:500])
        
        # Process each entry
        for entry in body.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event.get("sender", {}).get("id")
                
                if not sender_id:
                    continue
                
                # Handle different event types
                if "message" in messaging_event:
                    await _handle_message(sender_id, messaging_event["message"])
                elif "postback" in messaging_event:
                    await _handle_postback(sender_id, messaging_event["postback"])
                
        return JSONResponse({"status": "ok"})
        
    except Exception as e:
        _log.exception("Error processing Facebook message")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


async def _handle_message(sender_id: str, message: dict):
    """Handle incoming text or attachment message."""
    session_id = f"fb_{sender_id}"
    database.ensure_session(session_id)
    
    # Extract text
    text = message.get("text", "")
    
    # Handle attachments (images for try-on)
    attachments = message.get("attachments", [])
    image_url = None
    if attachments:
        for attachment in attachments:
            if attachment.get("type") == "image":
                image_url = attachment.get("payload", {}).get("url")
                if not text:
                    text = "[image received]"
                break
    
    if not text:
        return
    
    log_user_input(session_id, text)
    
    # Process through orchestrator
    from orchestrator import classify_intent, build_plan, rewrite_query
    from executor import execute_plan
    
    user_context = database.load_history(session_id, limit=6)
    context_str = "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')[:100]}" for m in user_context])
    
    intent = classify_intent(text, context_str)
    
    if intent == "chitchat":
        reply_text = _handle_chitchat(text, session_id)
        await _send_text_message(sender_id, reply_text)
        return
    
    query = rewrite_query(text, context_str)
    plan = build_plan(query, intent, channel_caps=FB_MESSENGER)
    
    result = execute_plan(
        plan=plan,
        session_id=session_id,
        user_input=text,
        channel_caps=FB_MESSENGER,
    )
    
    log_event("facebook_response", session_id=session_id, intent=intent,
              tool=result.get("tool"), channel="facebook")
    
    # Send formatted response
    await _send_formatted_response(sender_id, result)


async def _handle_postback(sender_id: str, postback: dict):
    """Handle button/postback clicks."""
    payload = postback.get("payload", "")
    session_id = f"fb_{sender_id}"
    
    _log.info("Facebook postback received: %s from %s", payload, sender_id)
    
    # Parse payload actions
    if payload.startswith("add_"):
        product_id = payload.replace("add_", "")
        # Add to cart via CartAgent
        from executor import execute_plan
        plan = [{
            "step": 1,
            "agent": "CartAgent",
            "input": {
                "action": "add",
                "product_id": product_id,
                "session_id": session_id,
                "channel_caps": FB_MESSENGER,
            }
        }]
        result = execute_plan(plan, session_id, user_input=f"add product {product_id}", channel_caps=FB_MESSENGER)
        await _send_text_message(sender_id, result.get("text", "Added to cart!"))
        
    elif payload.startswith("detail_"):
        product_id = payload.replace("detail_", "")
        # Could fetch product details and send
        import database as db
        product = db.get_product_by_id(int(product_id))
        if product:
            text = f"*{product['name']}*\nRs.{product['price']}\n{product.get('description', 'No description')}"
            await _send_text_message(sender_id, text)
        else:
            await _send_text_message(sender_id, "Product not found.")
            
    elif payload == "view_cart":
        from executor import execute_plan
        plan = [{
            "step": 1,
            "agent": "CartAgent",
            "input": {"action": "view", "session_id": session_id, "channel_caps": FB_MESSENGER}
        }]
        result = execute_plan(plan, session_id, user_input="view cart", channel_caps=FB_MESSENGER)
        await _send_text_message(sender_id, result.get("text", "Here's your cart!"))
        
    elif payload == "checkout":
        cart = database.db_get_cart(session_id)
        if cart:
            order_ids = database.place_order(session_id)
            if order_ids:
                await _send_text_message(sender_id, f"Order placed! Order IDs: {', '.join(map(str, order_ids))}")
            else:
                await _send_text_message(sender_id, "Checkout failed. Please try again.")
        else:
            await _send_text_message(sender_id, "Your cart is empty!")
    else:
        await _send_text_message(sender_id, f"You selected: {payload}")


def _handle_chitchat(message: str, session_id: str) -> str:
    """Handle chitchat for Facebook."""
    try:
        from llm import call_llm
        system = (
            "You are a friendly shopping assistant for SmartShop on Facebook Messenger. "
            "Keep responses concise and engaging. Use emojis occasionally. "
            "Guide users to search for products, view cart, or get recommendations."
        )
        return call_llm(system, message, temperature=0.7)
    except Exception:
        return "Hi! 👋 I'm your SmartShop assistant. Try 'search shirts' or 'show my cart'!"


async def _send_formatted_response(sender_id: str, result: dict):
    """Format and send response based on Facebook capabilities."""
    fb_template = result.get("fb_template")
    
    if fb_template and fb_template.get("type") == "generic":
        # Send carousel with product cards
        await _send_generic_template(sender_id, fb_template["elements"])
    else:
        # Send simple text
        text = result.get("text", "Here you go!")
        await _send_text_message(sender_id, text)


async def _send_text_message(sender_id: str, text: str):
    """Send a simple text message."""
    await _send_message(sender_id, {"text": text[:2000]})


async def _send_generic_template(sender_id: str, elements: list[dict]):
    """Send a generic template (carousel) with product cards."""
    payload = {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "generic",
                "elements": elements[:10],  # Max 10
            },
        }
    }
    await _send_message(sender_id, payload)


async def _send_message(sender_id: str, message_payload: dict):
    """Send message via Facebook Messenger Send API."""
    import aiohttp
    
    token = getattr(config, 'FB_PAGE_ACCESS_TOKEN', None)
    if not token:
        _log.error("Facebook Page Access Token not configured")
        return
    
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={token}"
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "recipient": {"id": sender_id},
        "message": message_payload,
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    _log.error("Facebook API error: %s", error_text)
    except Exception as e:
        _log.exception("Failed to send Facebook message")


@router.post("/send")
async def send_message(recipient_id: str, message: str):
    """Admin endpoint to send a message to a Facebook user."""
    await _send_text_message(recipient_id, message)
    return {"status": "sent"}
