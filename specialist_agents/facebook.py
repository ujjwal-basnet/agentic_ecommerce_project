"""Facebook Specialist Agent — direct REST API, no MCP.

Posts product images + captions to a configured Facebook Page.
Triggered from the owner dashboard "Post to Facebook" checkbox / button.
"""

import logging
import uuid
from pathlib import Path

import requests
import config

_log = logging.getLogger(__name__)


def post_to_page(image_bytes: bytes, caption: str, filename: str = "post.jpg") -> dict:
    """Post an image with caption to the configured Facebook Page.

    Args:
        image_bytes: raw image bytes
        caption: post caption text
        filename: original filename (for extension)

    Returns:
        dict with keys: success, post_id, message
    """
    if not config.facebook_enabled():
        return {"success": False, "message": "Facebook API credentials not configured."}

    # Save image locally
    ext = Path(filename).suffix or ".jpg"
    save_dir = Path("uploads/facebook_posts")
    save_dir.mkdir(parents=True, exist_ok=True)
    image_path = save_dir / f"fb_{uuid.uuid4().hex[:8]}{ext}"
    image_path.write_bytes(image_bytes)

    url = (
        f"https://graph.facebook.com/{config.FB_GRAPH_VERSION}/"
        f"{config.FB_PAGE_ID}/photos"
    )

    try:
        _log.info("Posting to Facebook Page %s …", config.FB_PAGE_ID)
        with open(image_path, "rb") as f:
            resp = requests.post(
                url,
                files={"source": f},
                data={
                    "caption": caption,
                    "published": "true",
                    "access_token": config.FB_PAGE_ACCESS_TOKEN,
                },
                timeout=60,
            )

        if resp.status_code == 200:
            post_id = resp.json().get("id", "")
            _log.info("Facebook post OK: %s", post_id)
            return {"success": True, "post_id": post_id, "message": "Posted to Facebook!"}
        else:
            _log.warning("Facebook API error: %s", resp.text[:300])
            return {"success": False, "message": f"Facebook API error: {resp.text[:200]}"}
    except Exception as exc:
        _log.exception("Facebook post failed")
        return {"success": False, "message": f"Facebook post failed: {str(exc)[:200]}"}
