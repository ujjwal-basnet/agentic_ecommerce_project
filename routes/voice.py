"""Voice/Phone API endpoint for function calling.

Provides a simple JSON API for voice assistants (Twilio, custom IVR, 
Siri, Alexa, etc.) that use function calling instead of MCP.

All responses are text-only optimized for text-to-speech.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

import database
from channels.capabilities import VOICE
from logs import log_event, log_user_input

router = APIRouter(prefix="/api/voice")
_log = logging.getLogger("smartshop.voice")


@router.post("/chat")
async def voice_chat(request: Request):
    """Main voice endpoint. Accepts text, returns voice-friendly response.
    
    Request body:
    {
        "message": "find red shirts",
        "session_id": "voice_12345",  // optional
        "user_id": "user_abc"         // optional, used to generate session
    }
    
    Response:
    {
        "text": "Found 3 red shirts...",
        "ssml": "<speak>Found <say-as interpret-as='cardinal'>3</say-as> red shirts...</speak>",
        "actions": ["Say 1 to add first item", "Say 2 for second item"],
        "session_id": "voice_12345"
    }
    """
    try:
        body = await request.json()
        
        text = body.get("message", "").strip()
        user_id = body.get("user_id", "")
        session_id = body.get("session_id", "")
        
        if not text:
            return JSONResponse({
                "text": "I didn't hear anything. What would you like to search for?",
                "ssml": "<speak>I didn't hear anything. What would you like to search for?</speak>",
                "session_id": session_id,
            })
        
        # Generate session ID if not provided
        if not session_id and user_id:
            session_id = f"voice_{user_id}"
        elif not session_id:
            import uuid
            session_id = f"voice_{uuid.uuid4().hex[:8]}"
        
        database.ensure_session(session_id)
        log_user_input(session_id, text)
        
        _log.info("Voice request: %s (session: %s)", text, session_id)
        
        # Process through orchestrator with VOICE channel capabilities
        from orchestrator import classify_intent, build_plan, rewrite_query
        from executor import execute_plan
        
        user_context = database.load_history(session_id, limit=3)  # Shorter for voice
        context_str = "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')[:50]}" for m in user_context])
        
        intent = classify_intent(text, context_str)
        
        # Handle chitchat
        if intent == "chitchat":
            reply = _handle_voice_chitchat(text, session_id)
            return JSONResponse({
                "text": reply,
                "ssml": f"<speak>{reply}</speak>",
                "session_id": session_id,
            })
        
        query = rewrite_query(text, context_str)
        plan = build_plan(query, intent, channel_caps=VOICE)
        
        result = execute_plan(
            plan=plan,
            session_id=session_id,
            user_input=text,
            channel_caps=VOICE,
        )
        
        log_event("voice_response", session_id=session_id, intent=intent,
                  tool=result.get("tool"), channel="voice")
        
        # Build voice-friendly response
        response = _format_voice_response(result, session_id)
        
        return JSONResponse(response)
        
    except Exception as e:
        _log.exception("Error processing voice request")
        return JSONResponse({
            "text": "I'm sorry, something went wrong. Please try again.",
            "ssml": "<speak>I'm sorry, something went wrong. Please try again.</speak>",
            "error": str(e),
            "session_id": session_id if 'session_id' in locals() else "",
        }, status_code=500)


@router.post("/function")
async def function_call(request: Request):
    """Function calling endpoint for OpenAI-style function calling.
    
    This endpoint accepts function call requests from LLMs that support
    function calling (OpenAI, Anthropic, etc.) for voice assistants.
    
    Request body (OpenAI format):
    {
        "functions": [
            {"name": "search_products", "parameters": {"query": "red shirts"}}
        ],
        "session_id": "voice_123"
    }
    
    Response:
    {
        "results": [
            {"function": "search_products", "result": {...}}
        ]
    }
    """
    try:
        body = await request.json()
        functions = body.get("functions", [])
        session_id = body.get("session_id", "")
        
        if not session_id:
            import uuid
            session_id = f"voice_{uuid.uuid4().hex[:8]}"
        
        results = []
        
        for func in functions:
            name = func.get("name", "")
            params = func.get("parameters", {})
            
            result = await _execute_function(name, params, session_id)
            results.append({
                "function": name,
                "result": result,
            })
        
        return JSONResponse({
            "results": results,
            "session_id": session_id,
        })
        
    except Exception as e:
        _log.exception("Error executing function")
        return JSONResponse({
            "error": str(e),
        }, status_code=500)


async def _execute_function(name: str, params: dict, session_id: str) -> dict:
    """Execute a single function call."""
    from executor import execute_plan
    from orchestrator import Intent
    
    if name == "search_products":
        plan = [{
            "step": 1,
            "agent": "SearchAgent",
            "input": {
                "query": params.get("query", ""),
                "session_id": session_id,
                "channel_caps": VOICE,
            }
        }]
        result = execute_plan(plan, session_id, user_input=params.get("query", ""), channel_caps=VOICE)
        return {
            "text": result.get("text", ""),
            "products": result.get("data", []),
        }
    
    elif name == "add_to_cart":
        plan = [{
            "step": 1,
            "agent": "CartAgent",
            "input": {
                "action": "add",
                "product_name": params.get("product_name", ""),
                "quantity": params.get("quantity", 1),
                "session_id": session_id,
                "channel_caps": VOICE,
            }
        }]
        result = execute_plan(plan, session_id, user_input=f"add {params.get('product_name', '')}", channel_caps=VOICE)
        return {"text": result.get("text", "Added to cart")}
    
    elif name == "view_cart":
        plan = [{
            "step": 1,
            "agent": "CartAgent",
            "input": {"action": "view", "session_id": session_id, "channel_caps": VOICE}
        }]
        result = execute_plan(plan, session_id, user_input="view cart", channel_caps=VOICE)
        return {"text": result.get("text", ""), "cart": result.get("data", [])}
    
    elif name == "checkout":
        cart = database.db_get_cart(session_id)
        if cart:
            order_ids = database.place_order(session_id)
            if order_ids:
                return {"success": True, "order_ids": order_ids}
            else:
                return {"success": False, "error": "Checkout failed"}
        else:
            return {"success": False, "error": "Cart is empty"}
    
    elif name == "get_recommendations":
        plan = [{
            "step": 1,
            "agent": "RecommendAgent",
            "input": {"user_input": "recommendations", "session_id": session_id, "channel_caps": VOICE}
        }]
        result = execute_plan(plan, session_id, user_input="recommendations", channel_caps=VOICE)
        return {
            "text": result.get("text", ""),
            "products": result.get("data", []),
        }
    
    else:
        return {"error": f"Unknown function: {name}"}


def _handle_voice_chitchat(message: str, session_id: str) -> str:
    """Handle chitchat for voice - keep it short and natural."""
    try:
        from llm import call_llm
        system = (
            "You are a friendly voice shopping assistant for SmartShop. "
            "Keep responses VERY short (1-2 sentences max). Speak naturally. "
            "Guide users to search for products or manage their cart."
        )
        return call_llm(system, message, temperature=0.7)
    except Exception:
        # Short, speakable defaults
        msg_lower = message.lower().strip()
        if any(w in msg_lower for w in ["hi", "hello", "hey"]):
            return "Hi there! What can I help you shop for today?"
        elif "bye" in msg_lower:
            return "Goodbye! Happy shopping!"
        elif "thank" in msg_lower:
            return "You're welcome! Need anything else?"
        else:
            return "I can help you find products, check your cart, or place an order. What would you like to do?"


def _format_voice_response(result: dict, session_id: str) -> dict:
    """Format result for voice output."""
    text = result.get("text", "")
    ssml = result.get("ssml", f"<speak>{text}</speak>")
    
    # Build action suggestions based on data
    actions = []
    data = result.get("data", [])
    
    if isinstance(data, list) and data:
        # It's a product list
        actions = [f"Say 'add {i + 1}' to add {p.get('name', 'item')} to cart" 
                   for i, p in enumerate(data[:3])]
        if len(data) > 3:
            actions.append(f"Or say 'more' to hear {len(data) - 3} other items")
    elif isinstance(data, dict) and data.get("cart_count"):
        actions = ["Say 'checkout' to place your order", "Say 'add more' to keep shopping"]
    
    response = {
        "text": text,
        "ssml": ssml,
        "session_id": session_id,
    }
    
    if actions:
        response["actions"] = actions
    
    return response


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "voice"}
