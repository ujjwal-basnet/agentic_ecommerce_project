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
    if hub_mode == "subscribe" and hub_verify_token == config.META_VERIFY_TOKEN:
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
    """Send plain text message to Facebook Messenger (uses Page Access Token)."""
    import aiohttp

    token = _page_token()
    page_id = getattr(config, "FB_PAGE_ID", None)

    if not token or not page_id:
        raise RuntimeError("Facebook not configured")

    url = f"{GRAPH_API_BASE}/{page_id}/messages"
    payload = {"recipient": {"id": sender_id}, "message": {"text": text}}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, params={"access_token": token}, timeout=10) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Facebook API error: {await resp.text()}")


def _page_token() -> str | None:
    """Prefer an explicit Page Access Token; fall back to META_ACCESS_TOKEN.
    Posting to /{page_id}/photos and /{page_id}/feed requires a Page token,
    not a User token. Get one via /{page_id}?fields=access_token."""
    return getattr(config, "FB_PAGE_ACCESS_TOKEN", None) or getattr(config, "META_ACCESS_TOKEN", None)


async def post_photo_to_page(
    image_url: str | None = None,
    caption: str = "",
    image_bytes: bytes | None = None,
    filename: str = "photo.png",
    content_type: str = "image/png",
) -> bool:
    """Post a photo to the Facebook Page feed.

    Rule: access_token → params (URL), everything else → json body.
    - image_url path: POST json={"url": ..., "message": ...}, params={access_token}.
    - image_bytes path: binary requires multipart, so we fall back to form-data
      (source + message in body), access_token still in params.
    """
    import aiohttp

    token = _page_token()
    page_id = getattr(config, "FB_PAGE_ID", None)
    if not token or not page_id:
        raise RuntimeError("Facebook credentials not configured for posting")
    if not image_url and not image_bytes:
        raise RuntimeError("post_photo_to_page requires image_url or image_bytes")

    url = f"{GRAPH_API_BASE}/{page_id}/photos"
    query = {"access_token": token}

    async with aiohttp.ClientSession() as session:
        if image_bytes is not None:
            form = aiohttp.FormData()
            form.add_field("source", image_bytes, filename=filename, content_type=content_type)
            if caption:
                form.add_field("message", caption)
            async with session.post(url, data=form, params=query, timeout=60) as resp:
                data = await resp.json()
        else:
            body = {"url": image_url}
            if caption:
                body["message"] = caption
            async with session.post(url, json=body, params=query, timeout=30) as resp:
                data = await resp.json()

        if "id" in data:
            _log.info("Facebook photo posted: %s", data["id"])
            return True
        raise RuntimeError(f"Facebook photo post failed: {data}")


async def post_feed_message(message: str) -> bool:
    """Post a text message to the Facebook Page feed.
    Rule: access_token → params, message → json body."""
    import aiohttp

    token = _page_token()
    page_id = getattr(config, "FB_PAGE_ID", None)

    if not token or not page_id:
        raise RuntimeError("Facebook credentials not configured for posting")

    url = f"{GRAPH_API_BASE}/{page_id}/feed"

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url, json={"message": message}, params={"access_token": token}, timeout=10
        ) as resp:
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
