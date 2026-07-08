"""Upload meme images and rebuild the Pinecone meme namespace.

Run from the repo root:

    .venv/bin/python scripts/rebuild_meme_rag.py

The script clears only PINECONE_MEME_NAMESPACE, not the product namespace.
"""

from __future__ import annotations

import argparse
import mimetypes
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=None, help="Meme source directory")
    parser.add_argument("--no-clear", action="store_true", help="Do not clear namespace first")
    parser.add_argument("--skip-upload", action="store_true", help="Use local image paths only")
    return parser.parse_args()


def _copy_local_assets(assets: list[dict], target_dir: Path) -> dict[str, str]:
    target_dir.mkdir(parents=True, exist_ok=True)
    image_urls: dict[str, str] = {}
    for asset in assets:
        src = Path(str(asset["source_image_path"]))
        dest = target_dir / src.name
        shutil.copy2(src, dest)
        image_urls[str(asset["asset_id"])] = f"data/memes/{dest.name}"
    return image_urls


def _upload_supabase_assets(assets: list[dict]) -> dict[str, str]:
    from api import config
    from api.integrations import storage

    if not (config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY):
        return {}

    storage.ensure_public_bucket(config.MEME_SUPABASE_BUCKET)
    image_urls: dict[str, str] = {}
    for asset in assets:
        path = Path(str(asset["source_image_path"]))
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        public_url = storage.upload(
            config.MEME_SUPABASE_BUCKET,
            path.name,
            path.read_bytes(),
            content_type=content_type,
        )
        if public_url:
            image_urls[str(asset["asset_id"])] = public_url
            print(f"uploaded {asset['asset_id']} -> {public_url}")
    return image_urls


def main() -> None:
    load_dotenv()

    from api import config
    from api.rag.meme_store import (
        load_meme_assets,
        rebuild_meme_namespace_sync,
        search_memes_sync,
    )

    args = _parse_args()
    source_dir = args.source or config.MEME_RAG_SOURCE_DIR
    assets = load_meme_assets(source_dir)
    if not assets:
        raise RuntimeError(f"No meme assets found in {source_dir}")

    local_urls = _copy_local_assets(assets, Path(config.MEME_ASSETS_DIR))
    remote_urls = {} if args.skip_upload else _upload_supabase_assets(assets)
    image_urls = {**local_urls, **remote_urls}

    result = rebuild_meme_namespace_sync(
        source_dir=source_dir,
        image_urls=image_urls,
        clear=not args.no_clear,
    )
    print(
        f"rebuilt namespace={result['namespace']} records={result['records']} "
        f"cleared={result['cleared']}"
    )

    for query in [
        "hi",
        "sorry my order is late",
        "is this premium and durable",
        "bruh ridiculous demand",
    ]:
        hits = search_memes_sync(query, top_k=1)
        if not hits:
            print(f"test query={query!r} -> no hit")
            continue
        hit = hits[0]
        print(
            f"test query={query!r} -> {hit.get('asset_id')} "
            f"score={hit.get('score'):.3f}"
        )


if __name__ == "__main__":
    main()
