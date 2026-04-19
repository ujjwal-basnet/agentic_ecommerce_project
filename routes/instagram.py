"""Instagram webhook — uses engine.run_text().
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import PlainTextResponse

import config
import database
import engine
from schemas import SocialPostResponse

router = APIRouter(prefix="/api/instagram")
_log = logging.getLogger("smartshop.instagram")

GRAPH_API_BASE = f"https://graph.facebook.com/{config.FB_GRAPH_VERSION}"


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query("", alias="hub.mode"),
    hub_verify_token: str = Query("", alias="hub.verify_token"),
    hub_challenge: str = Query("", alias="hub.challenge"),
):
    """Verify webhook with Instagram."""
    if hub_mode == "subscribe" and hub_verify_token == config.META_VERIFY_TOKEN:
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


async def publish_photo_to_instagram(image_url: str, caption: str) -> bool:
    """Publish a photo post to the Instagram Business feed via Graph API (2-step).
    Rule: access_token → params, everything else → json body.
    Note: IG's photo API has no binary upload — image_url MUST be publicly
    reachable. Configure SUPABASE_URL/SUPABASE_SERVICE_KEY or PUBLIC_BASE_URL."""
    import asyncio
    import aiohttp

    token = (
        getattr(config, "FB_PAGE_ACCESS_TOKEN", None)
        or getattr(config, "META_ACCESS_TOKEN", None)
    )
    ig_user_id = getattr(config, "IG_USER_ID", None)
    if not token or not ig_user_id:
        raise RuntimeError("Instagram not configured (IG_USER_ID / META_ACCESS_TOKEN)")

    async with aiohttp.ClientSession() as session:
        container_url = f"{GRAPH_API_BASE}/{ig_user_id}/media"
        container_body = {"image_url": image_url}
        if caption:
            container_body["caption"] = caption
        async with session.post(
            container_url, json=container_body, params={"access_token": token}, timeout=30
        ) as resp:
            data = await resp.json()
            creation_id = data.get("id")
            if not creation_id:
                raise RuntimeError(f"Instagram container failed: {data}")

        # Graph API recommends a brief wait so the media is processed before publish.
        await asyncio.sleep(5)

        publish_url = f"{GRAPH_API_BASE}/{ig_user_id}/media_publish"
        async with session.post(
            publish_url,
            json={"creation_id": creation_id},
            params={"access_token": token},
            timeout=15,
        ) as resp:
            data = await resp.json()
            if "id" in data:
                _log.info("Instagram photo published: %s", data["id"])
                return True
            raise RuntimeError(f"Instagram publish failed: {data}")
