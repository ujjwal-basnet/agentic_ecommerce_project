"""Shared Meta Graph API helpers for Facebook and Instagram routes."""

from __future__ import annotations

import hashlib
import hmac

from api import config


def verify_meta_signature(body: bytes, signature: str | None) -> bool:
    """Verify `x-hub-signature-256` using META_APP_SECRET."""
    if not config.META_APP_SECRET:
        return True
    if not signature or not signature.startswith("sha256="):
        return False
    expected = hmac.new(
        config.META_APP_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature.removeprefix("sha256="), expected)


def page_access_token() -> str:
    return config.FB_PAGE_ACCESS_TOKEN or config.META_ACCESS_TOKEN
