"""
Token Manager
-------------
- Saves the access token + expiry to token_store.json
- Refreshes it automatically before it expires (Instagram long-lived tokens last 60 days)
- Call get_token() anywhere to get a valid token
"""

import json
import os
import time
import requests
from wf_config import APP_ID, APP_SECRET, GRAPH_API_BASE, ACCESS_TOKEN

TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token_store.json")

# Refresh when less than 10 days remain
REFRESH_THRESHOLD_DAYS = 10


def _load_store() -> dict:
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            return json.load(f)
    return {}


def _save_store(data: dict):
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print("[token_manager] Token store saved.")


def save_token(token: str, expires_in_seconds: int | None = None):
    """Persist a token. expires_in_seconds comes from Meta's API response."""
    store = _load_store()
    store["access_token"] = token
    store["saved_at"] = time.time()
    # Instagram long-lived tokens expire in 60 days if not specified
    store["expires_in"] = expires_in_seconds or (60 * 24 * 3600)
    _save_store(store)


def get_token() -> str:
    """Return a valid access token, refreshing if close to expiry."""
    store = _load_store()
    token = store.get("access_token") or ACCESS_TOKEN
    if not token:
        print("[token_manager] WARNING: No access token found. Set ACCESS_TOKEN env var.")
        return ""

    saved_at = store.get("saved_at", 0)
    expires_in = store.get("expires_in", 60 * 24 * 3600)
    age_seconds = time.time() - saved_at
    remaining_seconds = expires_in - age_seconds
    remaining_days = remaining_seconds / 86400

    if remaining_days < REFRESH_THRESHOLD_DAYS:
        print(f"[token_manager] Token expires in {remaining_days:.1f} days — refreshing...")
        token = _refresh_token(token) or token

    return token


def _refresh_token(current_token: str) -> str:
    """Exchange current long-lived token for a new one."""
    url = f"{GRAPH_API_BASE}/oauth/access_token"
    params = {
        "grant_type": "ig_refresh_token",
        "access_token": current_token,
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if "access_token" in data:
            save_token(data["access_token"], data.get("expires_in"))
            print("[token_manager] Token refreshed successfully.")
            return data["access_token"]
        else:
            print(f"[token_manager] Refresh failed: {data}")
            return ""
    except Exception as e:
        print(f"[token_manager] Refresh error: {e}")
        return ""


def check_and_refresh():
    """Called by the scheduler periodically."""
    print("[token_manager] Checking token expiry...")
    get_token()


if __name__ == "__main__":
    token = input("Paste your Instagram access token: ").strip()
    save_token(token)
    print("Token saved.")
