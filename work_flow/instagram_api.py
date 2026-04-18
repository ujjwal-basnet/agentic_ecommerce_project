"""
Instagram Graph API helpers
----------------------------
- reply_to_dm(sender_id, message)
- reply_to_comment(comment_id, message)
- update_webhook_url(new_url)
- create_post(image_url, caption)
- publish_post(creation_id)
"""

import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
from config import APP_ID, APP_SECRET, IG_USER_ID, FB_PAGE_ID, VERIFY_TOKEN, GRAPH_API_BASE
from token_manager import get_token


def _token():
    return get_token()


# ── DMs ──────────────────────────────────────────────────────────────────────

PAGE_ID = FB_PAGE_ID


def reply_to_dm(sender_id: str, message: str, platform: str = "facebook") -> bool:
    """Send a DM reply. platform = 'facebook' or 'instagram'."""
    # Both use the same endpoint format but different account IDs
    account_id = IG_USER_ID if platform == "instagram" else PAGE_ID
    url = f"{GRAPH_API_BASE}/{account_id}/messages"
    payload = {
        "recipient": {"id": sender_id},
        "message": {"text": message},
    }
    r = requests.post(url, params={"access_token": _token()}, json=payload, timeout=10)
    if r.ok:
        print(f"[api] {platform.upper()} DM sent to {sender_id}")
        return True
    print(f"[api] {platform.upper()} DM failed: {r.status_code} {r.text}")
    return False


# ── Comments ─────────────────────────────────────────────────────────────────

def reply_to_comment(comment_id: str, message: str) -> bool:
    """Reply to an Instagram comment."""
    url = f"{GRAPH_API_BASE}/{comment_id}/replies"
    payload = {
        "message": message,
        "access_token": _token(),
    }
    r = requests.post(url, params=payload, timeout=10)
    if r.ok:
        print(f"[api] Comment reply sent to {comment_id}")
        return True
    print(f"[api] Comment reply failed: {r.status_code} {r.text}")
    return False


# ── Post Publishing ───────────────────────────────────────────────────────────

def create_image_container(image_url: str, caption: str) -> str | None:
    """Step 1: Upload image and get a creation ID."""
    url = f"{GRAPH_API_BASE}/{IG_USER_ID}/media"
    params = {
        "image_url": image_url,
        "caption": caption,
        "access_token": _token(),
    }
    r = requests.post(url, params=params, timeout=30)
    data = r.json()
    if "id" in data:
        print(f"[api] Media container created: {data['id']}")
        return data["id"]
    print(f"[api] Media container failed: {data}")
    return None


def publish_post(creation_id: str) -> bool:
    """Step 2: Publish the uploaded media container."""
    url = f"{GRAPH_API_BASE}/{IG_USER_ID}/media_publish"
    params = {
        "creation_id": creation_id,
        "access_token": _token(),
    }
    r = requests.post(url, params=params, timeout=10)
    data = r.json()
    if "id" in data:
        print(f"[api] Post published: {data['id']}")
        return True
    print(f"[api] Publish failed: {data}")
    return False


# ── Facebook Page Photo Post ──────────────────────────────────────────────────

def post_photo_to_facebook(image_url: str, caption: str) -> bool:
    """Post a photo to the Facebook Page feed."""
    url = f"{GRAPH_API_BASE}/{PAGE_ID}/photos"
    params = {
        "url": image_url,
        "message": caption,
        "access_token": _token(),
    }
    r = requests.post(url, params=params, timeout=30)
    data = r.json()
    if "id" in data:
        print(f"[api] Facebook photo posted: {data['id']}")
        return True
    print(f"[api] Facebook photo post failed: {data}")
    return False


# ── Webhook URL Update ────────────────────────────────────────────────────────

def update_webhook_url(new_url: str) -> bool:
    """Tell Meta to use a new webhook callback URL."""
    url = f"{GRAPH_API_BASE}/{APP_ID}/subscriptions"
    payload = {
        "object": "instagram",
        "callback_url": new_url,
        "verify_token": VERIFY_TOKEN,
        "fields": "messages,comments,mentions",
        "access_token": f"{APP_ID}|{APP_SECRET}",
    }
    r = requests.post(url, data=payload, timeout=10)
    if r.ok:
        print(f"[api] Webhook URL updated to: {new_url}")
        return True
    print(f"[api] Webhook update failed: {r.status_code} {r.text}")
    return False
