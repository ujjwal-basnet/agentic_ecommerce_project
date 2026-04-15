"""WhatsApp Business API webhook handler.

Routes incoming WhatsApp messages through the orchestrator
and formats responses for WhatsApp's limited UI capabilities.

Setup:
1. Get WhatsApp Business API credentials from Meta
2. Set WHATSAPP_API_TOKEN and WHATSAPP_PHONE_NUMBER_ID in .env
3. Configure webhook URL in Meta dashboard: https://your-domain.com/api/whatsapp/webhook
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

import config
import database
from channels.capabilities import WHATSAPP, get_channel
from log import log_event, log_user_input

router = APIRouter(prefix="/api/whatsapp")
_log = logging.getLogger("smartshop.whatsapp")


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = "",
    hub_verify_token: str = "",
    hub_challenge: str = "",
):
    """Verify webhook with Meta/WhatsApp.
    
    Meta sends a GET request to verify the webhook endpoint.
    We must return the challenge if the verify token matches.
    """
    expected_token = getattr(config, 'WHATSAPP_VERIFY_TOKEN', 'smartshop-webhook')
    
    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        _log.info("WhatsApp webhook verified")
        return Response(content=hub_challenge, media_type="text/plain")
    
    _log.warning("WhatsApp webhook verification failed")
    return Response(content="Verification failed", status_code=403)


@router.post("/webhook")
async def receive_message(request: Request):
    """Receive and process incoming WhatsApp messages."""
    try:
        body = await request.json()
        _log.debug("Received WhatsApp payload: %s", json.dumps(body)[:500])
        
        # Extract message data
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        
        if not messages:
            # Could be status update, not a message
            return JSONResponse({"status": "ok"})
        
        message = messages[0]
        from_number = message.get("from")  # Phone number
        message_type = message.get("type")
        
        # Generate session ID from phone number
        session_id = f"whatsapp_{from_number}"
        database.ensure_session(session_id)
        
        # Extract text or handle other message types
        if message_type == "text":
            text = message.get("text", {}).get("body", "")
        elif message_type == "interactive":
            # Button or list reply
            interactive = message.get("interactive", {})
            if interactive.get("type") == "button_reply":
                text = interactive.get("button_reply", {}).get("id", "")
            elif interactive.get("type") == "list_reply":
                text = interactive.get("list_reply", {}).get("id", "")
            else:
                text = ""
        elif message_type == "image":
            # Handle image (for try-on feature later)
            text = "[image received]"
        else:
            text = ""
        
        if not text:
            return JSONResponse({"status": "ok"})
        
        log_user_input(session_id, text)
        
        # Process through orchestrator with WhatsApp channel capabilities
        from orchestrator import classify_intent, build_plan, rewrite_query
        from executor import execute_plan
        
        user_context = database.load_history(session_id, limit=6)
        context_str = "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')[:100]}" for m in user_context])
        
        intent = classify_intent(text, context_str)
        
        if intent == "chitchat":
            reply_text = _handle_chitchat(text, session_id)
            await _send_whatsapp_message(from_number, reply_text)
            return JSONResponse({"status": "ok"})
        
        query = rewrite_query(text, context_str)
        plan = build_plan(query, intent, channel_caps=WHATSAPP)
        
        result = execute_plan(
            plan=plan,
            session_id=session_id,
            user_input=text,
            channel_caps=WHATSAPP,
        )
        
        log_event("whatsapp_response", session_id=session_id, intent=intent, 
                  tool=result.get("tool"), channel="whatsapp")
        
        # Format and send response
        await _send_formatted_response(from_number, result)
        
        return JSONResponse({"status": "ok"})
        
    except Exception as e:
        _log.exception("Error processing WhatsApp message")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


def _handle_chitchat(message: str, session_id: str) -> str:
    """Handle chitchat responses for WhatsApp."""
    try:
        from llm import call_llm
        system = (
            "You are a friendly shopping assistant for SmartShop on WhatsApp. "
            "Keep responses short (under 100 words) and helpful. "
            "Guide users to search for products, view cart, or get recommendations."
        )
        return call_llm(system, message, temperature=0.7)
    except Exception:
        return "Hi! I can help you shop. Try 'search shirts' or 'show my cart'."


async def _send_formatted_response(phone_number: str, result: dict):
    """Format result based on WhatsApp capabilities and send."""
    text = result.get("text", "Here you go!")
    quick_replies = result.get("quick_replies", [])
    
    # If we have quick replies, send interactive message
    if quick_replies and len(quick_replies) <= 10:
        await _send_interactive_message(phone_number, text, quick_replies)
    else:
        # Simple text message
        await _send_whatsapp_message(phone_number, text)


async def _send_whatsapp_message(phone_number: str, text: str):
    """Send a simple text message via WhatsApp Business API."""
    import aiohttp
    
    token = getattr(config, 'WHATSAPP_API_TOKEN', None)
    phone_id = getattr(config, 'WHATSAPP_PHONE_NUMBER_ID', None)
    
    if not token or not phone_id:
        _log.error("WhatsApp credentials not configured")
        return
    
    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_number,
        "type": "text",
        "text": {"body": text[:4096]},  # WhatsApp limit
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    _log.error("WhatsApp API error: %s", await resp.text())
    except Exception as e:
        _log.exception("Failed to send WhatsApp message")


async def _send_interactive_message(
    phone_number: str, 
    text: str, 
    quick_replies: list[dict[str, str]]
):
    """Send an interactive message with buttons/quick replies."""
    import aiohttp
    
    token = getattr(config, 'WHATSAPP_API_TOKEN', None)
    phone_id = getattr(config, 'WHATSAPP_PHONE_NUMBER_ID', None)
    
    if not token or not phone_id:
        _log.error("WhatsApp credentials not configured")
        return
    
    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    
    # Build action buttons
    buttons = [
        {
            "type": "reply",
            "reply": {
                "id": qr.get("payload", f"action_{i}"),
                "title": qr.get("title", "Action")[:20],  # 20 char limit
            }
        }
        for i, qr in enumerate(quick_replies[:3])  # Max 3 buttons
    ]
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text[:1024]},
            "action": {"buttons": buttons},
        },
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    _log.error("WhatsApp API error: %s", await resp.text())
    except Exception as e:
        _log.exception("Failed to send WhatsApp interactive message")


@router.post("/send")
async def send_message(phone_number: str, message: str):
    """Admin endpoint to send a message to a WhatsApp user."""
    await _send_whatsapp_message(phone_number, message)
    return {"status": "sent"}
