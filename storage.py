"""Supabase Storage helpers. Falls back to local disk when SUPABASE_URL is not set."""

from __future__ import annotations

import io
import requests

import config


def _configured() -> bool:
    return bool(config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY)


def upload(bucket: str, filename: str, data: bytes, content_type: str = "image/png") -> str | None:
    """Upload bytes to Supabase Storage bucket. Returns public URL, or None if not configured."""
    if not _configured():
        return None
    url = f"{config.SUPABASE_URL}/storage/v1/object/{bucket}/{filename}"
    r = requests.post(url, headers={
        "Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}",
        "Content-Type": content_type,
        "x-upsert": "true",
    }, data=data, timeout=30)
    r.raise_for_status()
    return f"{config.SUPABASE_URL}/storage/v1/object/public/{bucket}/{filename}"


def is_remote(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


def fetch_bytes(path_or_url: str) -> bytes:
    """Return raw bytes from a URL (Supabase) or local file path."""
    if is_remote(path_or_url):
        r = requests.get(path_or_url, timeout=15)
        r.raise_for_status()
        return r.content
    with open(path_or_url, "rb") as f:
        return f.read()
