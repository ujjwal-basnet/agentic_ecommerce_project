"""Upload local product images to Supabase Storage and update DB image_path URLs.

Run from repo root after setting .env:

    python3 scripts/sync_product_images_to_supabase.py

This keeps local data/products/* as development fallback while production uses
public Supabase Storage URLs in products.image_path.
"""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path

import psycopg2
import requests
from dotenv import load_dotenv


BUCKET = "product-images"


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def ensure_bucket(supabase_url: str, service_key: str) -> None:
    headers = {
        "Authorization": f"Bearer {service_key}",
        "apikey": service_key,
        "Content-Type": "application/json",
    }

    check_url = f"{supabase_url}/storage/v1/bucket/{BUCKET}"
    check = requests.get(check_url, headers=headers, timeout=30)
    if check.status_code == 200:
        return

    url = f"{supabase_url}/storage/v1/bucket"
    payload = {"id": BUCKET, "name": BUCKET, "public": True}
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    if response.status_code in {200, 201, 409}:
        return
    print(f"bucket create failed: {response.status_code} {response.text}")
    response.raise_for_status()


def upload_file(supabase_url: str, service_key: str, path: Path) -> str:
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    url = f"{supabase_url}/storage/v1/object/{BUCKET}/{path.name}"
    headers = {
        "Authorization": f"Bearer {service_key}",
        "apikey": service_key,
        "Content-Type": content_type,
        "x-upsert": "true",
    }
    response = requests.post(url, headers=headers, data=path.read_bytes(), timeout=60)
    if not response.ok:
        print(f"upload failed for {path}: {response.status_code} {response.text}")
    response.raise_for_status()
    return f"{supabase_url}/storage/v1/object/public/{BUCKET}/{path.name}"


def main() -> None:
    load_dotenv()
    database_url = require_env("DATABASE_URL")
    supabase_url = require_env("SUPABASE_URL").rstrip("/")
    service_key = require_env("SUPABASE_SERVICE_KEY")

    ensure_bucket(supabase_url, service_key)

    conn = psycopg2.connect(database_url, sslmode=os.getenv("DB_SSLMODE", "require"))
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, image_path FROM products ORDER BY id"
            )
            rows = cur.fetchall()

            updated = 0
            skipped = 0
            missing = 0
            for product_id, name, image_path in rows:
                image_path = image_path or ""
                if image_path.startswith(("http://", "https://")):
                    skipped += 1
                    continue

                path = Path(image_path)
                if not path.exists():
                    missing += 1
                    print(f"missing local image: id={product_id} name={name} path={image_path}")
                    continue

                public_url = upload_file(supabase_url, service_key, path)
                cur.execute(
                    "UPDATE products SET image_path = %s, updated_at = NOW() WHERE id = %s",
                    (public_url, product_id),
                )
                updated += 1
                print(f"updated id={product_id}: {public_url}")

        print(f"done updated={updated} skipped_remote={skipped} missing={missing}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
