"""
Ngrok URL Updater
-----------------
- Polls the local ngrok API to detect the current public URL
- If the URL changed (ngrok restarted), automatically updates Meta's webhook subscription
- Run as a background thread
"""

import time
import requests
from wf_config import NGROK_API_URL

_last_url: str = ""


def get_ngrok_url() -> str:
    """Fetch the current public ngrok URL from the local ngrok agent."""
    try:
        r = requests.get(NGROK_API_URL, timeout=5)
        tunnels = r.json().get("tunnels", [])
        for t in tunnels:
            if t.get("proto") == "https":
                return t["public_url"]
        if tunnels:
            return tunnels[0]["public_url"]
    except Exception as e:
        print(f"[ngrok_updater] Could not reach ngrok agent: {e}")
    return ""


def check_and_update():
    """Check if ngrok URL changed and update Meta's webhook if so."""
    global _last_url
    from instagram_api import update_webhook_url

    url = get_ngrok_url()
    if not url:
        return

    webhook_url = url.rstrip("/") + "/webhook"

    if webhook_url != _last_url:
        print(f"[ngrok_updater] URL changed: {_last_url!r} → {webhook_url!r}")
        success = update_webhook_url(webhook_url)
        if success:
            _last_url = webhook_url
    else:
        print(f"[ngrok_updater] URL unchanged: {webhook_url}")


def run_loop(interval_seconds: int = 60):
    """Continuously poll and update. Run in a background thread."""
    print("[ngrok_updater] Starting URL watcher...")
    while True:
        check_and_update()
        time.sleep(interval_seconds)
