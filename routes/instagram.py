"""Instagram webhook — uses engine.run_text().
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

import config
import database
import engine
from schemas import SocialPostResponse

router = APIRouter(prefix="/api/instagram")
_log = logging.getLogger("smartshop.instagram")

GRAPH_API_BASE = f"https://graph.facebook.com/{config.FB_GRAPH_VERSION}"


@router.get("/webhook")
async def verify_webhook(hub_mode: str = "", hub_verify_token: str = "", hub_challenge: str = ""):
    """Verify webhook with Instagram."""
    expected = getattr(config, 'IG_VERIFY_TOKEN', config.META_VERIFY_TOKEN)
    if hub_mode == "subscribe" and hub_verify_token == expected:
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="Verification failed", status_code=403)


@router.post("/webhook", response_model=SocialPostResponse)
async def receive_webhook(request: Request):
    """Receive Instagram DM and respond with plain text."""
    body = await request.body()
    
    # Verify signature
    signature = request.headers.get("x-hub-signature-256", "")
    if config.META_APP_SECRET and signature:
        expected = "sha256=" + hmac.new(config.META_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return PlainTextResponse(content="Invalid signature", status_code=403)
    
    try:
        payload = json.loads(body)
        for entry in payload.get("entry", []):
            # Handle DMs
            for msg in entry.get("messaging", []):
                await _handle_dm(msg)
        
        return PlainTextResponse(content="OK")
    except Exception as e:
        _log.exception("Instagram error: %s", e)
        raise


async def _handle_dm(msg: dict):
    """Process DM via engine and send text response."""
    sender_id = msg.get("sender", {}).get("id")
    text = msg.get("message", {}).get("text", "")
    is_echo = msg.get("message", {}).get("is_echo", False)
    
    if not sender_id or not text or is_echo:
        return
    
    session_id = f"ig_{sender_id}"
    database.ensure_session(session_id)
    
    # Engine handles plan → execute → format
    reply = await engine.run_text(text, session_id=session_id)
    await _send_dm(sender_id, reply[:1000])  # Instagram limit


async def _send_dm(sender_id: str, message: str):
    """Send plain text DM to Instagram."""
    import aiohttp
    
    token = getattr(config, 'META_ACCESS_TOKEN', None)
    ig_user_id = getattr(config, 'IG_USER_ID', None)
    
    if not token or not ig_user_id:
        raise RuntimeError("Instagram not configured")
    
    url = f"{GRAPH_API_BASE}/{ig_user_id}/messages"
    payload = {"recipient": {"id": sender_id}, "message": {"text": message}}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, params={"access_token": token}, timeout=10) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Instagram API error: {await resp.text()}")
