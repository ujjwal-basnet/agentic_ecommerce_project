"""Supabase Storage helpers. Falls back to local disk when SUPABASE_URL is not set.

Uses httpx for non-blocking async uploads (sync wrappers kept for backward compat).
"""

from __future__ import annotations

import io
import logging

import httpx
import requests

from api import config

logger = logging.getLogger(__name__)


def _configured() -> bool:
    return bool(config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY)


def ensure_public_bucket(bucket: str) -> bool:
    """Create a public Supabase Storage bucket if storage is configured."""
    if not _configured():
        return False
    try:
        headers = {
            "Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}",
            "apikey": config.SUPABASE_SERVICE_KEY,
            "Content-Type": "application/json",
        }
        check_url = f"{config.SUPABASE_URL}/storage/v1/bucket/{bucket}"
        check = requests.get(check_url, headers=headers, timeout=30)
        if check.status_code == 200:
            return True

        url = f"{config.SUPABASE_URL}/storage/v1/bucket"
        payload = {"id": bucket, "name": bucket, "public": True}
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code in {200, 201, 409}:
            return True
        response.raise_for_status()
        return True
    except Exception as e:
        logger.warning("Supabase ensure_public_bucket failed: %s", e)
        return False


def upload(
    bucket: str, filename: str, data: bytes, content_type: str = "image/png"
) -> str | None:
    """Sync upload — use async_upload from async code paths."""
    if not _configured():
        return None
    try:
        url = f"{config.SUPABASE_URL}/storage/v1/object/{bucket}/{filename}"
        r = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}",
                "apikey": config.SUPABASE_SERVICE_KEY,
                "Content-Type": content_type,
                "x-upsert": "true",
            },
            data=data,
            timeout=30,
        )
        r.raise_for_status()
        return f"{config.SUPABASE_URL}/storage/v1/object/public/{bucket}/{filename}"
    except Exception as e:
        logger.warning("Supabase upload failed: %s. Falling back to local storage.", e)
        return None


async def async_upload(
    bucket: str, filename: str, data: bytes, content_type: str = "image/png"
) -> str | None:
    """Non-blocking upload via httpx — use from async endpoints."""
    if not _configured():
        return None
    try:
        url = f"{config.SUPABASE_URL}/storage/v1/object/{bucket}/{filename}"
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}",
                    "apikey": config.SUPABASE_SERVICE_KEY,
                    "Content-Type": content_type,
                    "x-upsert": "true",
                },
                content=data,
            )
            r.raise_for_status()
        return f"{config.SUPABASE_URL}/storage/v1/object/public/{bucket}/{filename}"
    except Exception as e:
        logger.warning("Supabase async upload failed: %s. Falling back to local storage.", e)
        return None


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


async def async_fetch_bytes(path_or_url: str) -> bytes:
    """Non-blocking fetch via httpx."""
    if is_remote(path_or_url):
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(path_or_url)
            r.raise_for_status()
            return r.content
    with open(path_or_url, "rb") as f:
        return f.read()
