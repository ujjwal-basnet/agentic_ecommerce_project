"""Facebook Messenger webhook — uses engine.run_text().
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

import config
import database
import engine
from schemas import SocialPostResponse

router = APIRouter(prefix="/api/facebook")
_log = logging.getLogger("smartshop.facebook")

GRAPH_API_BASE = f"https://graph.facebook.com/{config.FB_GRAPH_VERSION}"


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query("", alias="hub.mode"),
    hub_verify_token: str = Query("", alias="hub.verify_token"),
    hub_challenge: str = Query("", alias="hub.challenge"),
):
    """Verify webhook with Facebook."""
    expected = getattr(config, 'FB_VERIFY_TOKEN', 'smartshop-webhook')
    if hub_mode == "subscribe" and hub_verify_token == expected:
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="Verification failed", status_code=403)


@router.post("/webhook", response_model=SocialPostResponse)
async def receive_message(request: Request):
    """Receive Facebook message and respond with plain text."""
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
            for event in entry.get("messaging", []):
                sender_id = event.get("sender", {}).get("id")
                if not sender_id or event.get("message", {}).get("is_echo"):
                    continue

                if "message" in event:
                    await _handle_message(sender_id, event["message"])

        return JSONResponse({"status": "ok"})
    except Exception as e:
        _log.exception("Facebook error: %s", e)
        raise


async def _handle_message(sender_id: str, message: dict):
    """Process message via engine and send text response."""
    session_id = f"fb_{sender_id}"
    database.ensure_session(session_id)

    text = message.get("text", "")
    if not text:
        return

    # Engine handles plan → execute → format
    reply = await engine.run_text(text, session_id=session_id)
    await _send_text(sender_id, reply[:2000])  # Facebook limit


async def _send_text(sender_id: str, text: str):
    """Send plain text message to Facebook."""
    import aiohttp

    token = getattr(config, 'META_ACCESS_TOKEN', None)
    page_id = getattr(config, 'FB_PAGE_ID', None)

    if not token or not page_id:
        raise RuntimeError("Facebook not configured")

    url = f"{GRAPH_API_BASE}/{page_id}/messages"
    payload = {"recipient": {"id": sender_id}, "message": {"text": text}}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, params={"access_token": token}, timeout=10) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Facebook API error: {await resp.text()}")


async def post_photo_to_page(image_url: str, caption: str) -> bool:
    """Post a photo to the Facebook Page feed."""
    import aiohttp

    token = getattr(config, 'META_ACCESS_TOKEN', None)
    page_id = getattr(config, 'FB_PAGE_ID', None)

    if not token or not page_id:
        raise RuntimeError("Facebook credentials not configured for posting")

    url = f"{GRAPH_API_BASE}/{page_id}/photos"
    params = {
        "url": image_url,
        "message": caption,
        "access_token": token,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params, timeout=30) as resp:
            data = await resp.json()
            if "id" in data:
                _log.info("Facebook photo posted: %s", data["id"])
                return True
            raise RuntimeError(f"Facebook photo post failed: {data}")


async def post_feed_message(message: str) -> bool:
    """Post a text message to the Facebook Page feed."""
    import aiohttp

    token = getattr(config, 'META_ACCESS_TOKEN', None)
    page_id = getattr(config, 'FB_PAGE_ID', None)

    if not token or not page_id:
        raise RuntimeError("Facebook credentials not configured for posting")

    url = f"{GRAPH_API_BASE}/{page_id}/feed"
    params = {
        "message": message,
        "access_token": token,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params, timeout=10) as resp:
            data = await resp.json()
            if "id" in data:
                _log.info("Facebook feed post created: %s", data["id"])
                return True
            raise RuntimeError(f"Facebook feed post failed: {data}")


@router.post("/post", response_model=SocialPostResponse)
async def create_page_post(image_url: str | None = None, caption: str = ""):
    """Admin endpoint to post to Facebook Page (photo or text)."""
    if image_url:
        success = await post_photo_to_page(image_url, caption)
    else:
        success = await post_feed_message(caption)

    if success:
        return {"status": "posted"}
    raise RuntimeError("Failed to create post")
