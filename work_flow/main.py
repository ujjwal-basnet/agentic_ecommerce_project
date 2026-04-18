"""Messenger/Instagram webhook — DM + comment replies powered by the main LLM engine."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import sys
import threading

# ── Make the parent project importable (engine, database, planner, tools, …) ──
_WF_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_WF_DIR)
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from wf_config import APP_SECRET, VERIFY_TOKEN, DM_FALLBACK_REPLY, COMMENT_FALLBACK_REPLY

# Local modules
import instagram_api
import ngrok_updater
import scheduler
import token_manager

# Parent-project AI stack
import engine
import database

log = logging.getLogger("workflow.webhook")
logging.basicConfig(level=logging.INFO)

app = FastAPI()


class NgrokMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["ngrok-skip-browser-warning"] = "true"
        return response


app.add_middleware(NgrokMiddleware)
app.mount("/static", StaticFiles(directory=os.path.join(_WF_DIR, "static")), name="static")


# ── AI reply helpers ──────────────────────────────────────────────────────────

async def _ai_dm_reply(platform: str, sender_id: str, text: str) -> str:
    """Generate a DM reply via the main planner/engine. Falls back on error."""
    session_id = f"{'ig' if platform == 'instagram' else 'fb'}_{sender_id}"
    try:
        database.ensure_session(session_id)
        reply = await engine.run_text(text, session_id=session_id)
        return (reply or DM_FALLBACK_REPLY)[:2000]  # Meta DM limit
    except Exception:
        log.exception("engine.run_text failed for %s/%s", platform, sender_id)
        return DM_FALLBACK_REPLY


async def _ai_comment_reply(comment_id: str, comment_text: str) -> str:
    """Generate a short, public-safe comment reply via the engine."""
    session_id = f"comment_{comment_id}"
    prompt = (
        f"A user left this public comment on our post: {comment_text!r}. "
        "Write a short (1-2 sentence), friendly public reply. No links unless they ask."
    )
    try:
        database.ensure_session(session_id)
        reply = await engine.run_text(prompt, session_id=session_id)
        return (reply or COMMENT_FALLBACK_REPLY)[:500]
    except Exception:
        log.exception("engine.run_text failed for comment %s", comment_id)
        return COMMENT_FALLBACK_REPLY


# ── Startup: launch background workers ────────────────────────────────────────

@app.on_event("startup")
def start_background_workers():
    # 1. Ngrok URL watcher — checks every 60s, updates Meta if URL changed
    threading.Thread(target=ngrok_updater.run_loop, args=(60,), daemon=True).start()

    # 2. Post scheduler — checks every 60s for due posts
    threading.Thread(target=scheduler.run_loop, args=(60,), daemon=True).start()

    # 3. Token refresh — checks every 24 hours
    def token_refresh_loop():
        import time
        while True:
            token_manager.check_and_refresh()
            time.sleep(24 * 3600)
    threading.Thread(target=token_refresh_loop, daemon=True).start()

    print("[startup] All background workers started.")


# ── Webhook verification (GET) ─────────────────────────────────────────────────

@app.get("/webhook")
async def verify_webhook(request: Request):
    hub_mode = request.query_params.get("hub.mode")
    hub_challenge = request.query_params.get("hub.challenge")
    hub_verify_token = request.query_params.get("hub.verify_token")

    print(f"[webhook] VERIFY mode={hub_mode} token={hub_verify_token}")
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge)
    return PlainTextResponse(content="Verification failed", status_code=403)


# ── Webhook events (POST) ──────────────────────────────────────────────────────

@app.post("/webhook")
async def receive_webhook(request: Request):
    body = await request.body()

    # Verify signature
    signature = request.headers.get("x-hub-signature-256", "")
    if APP_SECRET and signature:
        expected = "sha256=" + hmac.new(
            APP_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return PlainTextResponse(content="Invalid signature", status_code=403)

    try:
        payload = json.loads(body)
    except Exception:
        return PlainTextResponse(content="Bad JSON", status_code=400)

    print(f"[webhook] Event received: {json.dumps(payload, indent=2)}")

    platform = payload.get("object", "page")  # "page" = Facebook, "instagram" = Instagram
    platform_key = "instagram" if platform == "instagram" else "facebook"

    for entry in payload.get("entry", []):
        # ── DMs ──
        for messaging in entry.get("messaging", []):
            sender_id = messaging.get("sender", {}).get("id")
            message = messaging.get("message", {})
            text = message.get("text", "")
            is_echo = message.get("is_echo", False)
            recipient_id = messaging.get("recipient", {}).get("id")
            if sender_id and text and not is_echo and sender_id != recipient_id:
                print(f"[webhook] {platform_key.upper()} DM from {sender_id}: {text}")
                reply = await _ai_dm_reply(platform_key, sender_id, text)
                instagram_api.reply_to_dm(sender_id, reply, platform=platform_key)

        # ── Comments ──
        for change in entry.get("changes", []):
            value = change.get("value", {})
            if change.get("field") == "comments":
                comment_id = value.get("id")
                comment_text = value.get("text", "")
                if comment_id:
                    print(f"[webhook] Comment {comment_id}: {comment_text}")
                    reply = await _ai_comment_reply(comment_id, comment_text)
                    instagram_api.reply_to_comment(comment_id, reply)

    return PlainTextResponse(content="OK")


# ── Extra endpoints ────────────────────────────────────────────────────────────

@app.post("/schedule-post")
async def schedule_post_endpoint(request: Request):
    """
    Schedule a post via HTTP.
    Body: { "image_url": "...", "caption": "...", "scheduled_time": "YYYY-MM-DD HH:MM:SS" }
    """
    data = await request.json()
    image_url = data.get("image_url")
    caption = data.get("caption", "")
    scheduled_time = data.get("scheduled_time")
    if not image_url or not scheduled_time:
        return PlainTextResponse(content="image_url and scheduled_time required", status_code=400)
    scheduler.schedule_post(image_url, caption, scheduled_time)
    return PlainTextResponse(content="Post scheduled")


@app.get("/status")
async def status():
    """Health check — shows token age and pending posts."""
    store = token_manager._load_store()
    posts = scheduler._load_posts()
    pending = [p for p in posts if p["status"] == "pending"]
    ngrok_url = ngrok_updater.get_ngrok_url()
    return {
        "server": "running",
        "ngrok_url": ngrok_url,
        "token_saved_at": store.get("saved_at"),
        "pending_posts": len(pending),
        "ai_engine": "enabled",
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
