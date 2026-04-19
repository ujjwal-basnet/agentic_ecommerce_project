"""Supabase Storage helpers. Falls back to local disk when SUPABASE_URL is not set."""

from __future__ import annotations

import logging

import requests

import config

logger = logging.getLogger(__name__)

# Buckets this app reads/writes. Created on startup if missing.
BUCKETS = ("user-uploads", "product-images", "tryon-results", "campaign-images")


def _configured() -> bool:
    return bool(config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}",
        "apikey": config.SUPABASE_SERVICE_KEY,
    }


def ensure_buckets() -> None:
    """Create or upsert the app's Supabase buckets to public. No-op when unconfigured.
    Free tier Supabase includes 1 GB Storage + 5 GB egress — enough for this project.
    A *private* bucket makes /object/public/... return "Bucket not found" and breaks IG."""
    if not _configured():
        logger.info("Supabase Storage not configured — images fall back to local disk")
        return
    base = f"{config.SUPABASE_URL}/storage/v1/bucket"
    headers = {**_headers(), "Content-Type": "application/json"}
    for name in BUCKETS:
        try:
            r = requests.post(
                base,
                headers=headers,
                json={"id": name, "name": name, "public": True},
                timeout=10,
            )
            if r.status_code in (200, 201):
                logger.info("Supabase bucket created (public): %s", name)
                continue
            # Bucket already exists — force it public (fixes legacy private buckets).
            r2 = requests.put(
                f"{base}/{name}", headers=headers, json={"public": True}, timeout=10
            )
            if r2.ok:
                logger.info("Supabase bucket ensured public: %s", name)
            else:
                logger.warning(
                    "Supabase bucket %s update failed: %s %s",
                    name, r2.status_code, r2.text[:200],
                )
        except Exception as e:
            logger.warning("Supabase bucket %s ensure failed: %s", name, e)


def upload(bucket: str, filename: str, data: bytes, content_type: str = "image/png") -> str | None:
    """Upload bytes to Supabase Storage bucket. Returns public URL, or None if not configured."""
    if not _configured():
        return None
    url = f"{config.SUPABASE_URL}/storage/v1/object/{bucket}/{filename}"
    r = requests.post(
        url,
        headers={**_headers(), "Content-Type": content_type, "x-upsert": "true"},
        data=data,
        timeout=30,
    )
    r.raise_for_status()
    return f"{config.SUPABASE_URL}/storage/v1/object/public/{bucket}/{filename}"
