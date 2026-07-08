"""Pinecone-backed meme asset RAG.

The Pinecone index uses integrated text embedding, so records store rich text
descriptions plus scalar metadata that points at the hosted image URL.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any

from api import config
from api.rag.vector_store import get_pinecone_index

logger = logging.getLogger(__name__)

_DOC_IMAGE_STEM_OVERRIDES = {
    "aplology_cat_bouqet": "apology_cat_bouquet",
    "masha_deadpan_stare_descrription": "masha_deadpan_stare",
}

_GREETING_RE = re.compile(
    r"^\s*(hi+|hello+|hey+|yo+|sup|namaste|namaskar|ke xa|k xa|hello bot|hi bot)[!.\s]*$",
    re.IGNORECASE,
)

_MEME_TRIGGER_RE = re.compile(
    r"\b("
    r"hi|hello|hey|say hi|welcome|namaste|"
    r"sorry|apolog\w*|delay\w*|late|frustrat\w*|upset|angry|issue|problem|discount|out of stock|"
    r"durable|strong|premium|upgrade|pro|reliable|tough|best|warranty|heavy lifting|"
    r"bruh|ridiculous|absurd|nonsense|troll|obvious|unreasonable"
    r")\b",
    re.IGNORECASE,
)

_FORCE_QUERIES = {
    "eager_hello_cat": "hello greeting welcome eager friendly attentive cat says hello",
}


def _asset_id_for_doc(path: Path) -> str:
    return _DOC_IMAGE_STEM_OVERRIDES.get(path.stem, path.stem)


def _find_image(source_dir: Path, asset_id: str) -> Path | None:
    for suffix in (".png", ".jpg", ".jpeg", ".webp"):
        candidate = source_dir / f"{asset_id}{suffix}"
        if candidate.exists():
            return candidate
    return None


def _title(asset_id: str) -> str:
    return asset_id.replace("_", " ").title()


def _text_for_asset(asset_id: str, doc_text: str) -> str:
    return (
        f"Meme asset: {_title(asset_id)}\n"
        f"Asset id: {asset_id}\n"
        "Use this as a chat reaction image when the user's intent, emotion, "
        "or the assistant response matches the description.\n\n"
        f"{doc_text.strip()}"
    )


def load_meme_assets(source_dir: str | Path | None = None) -> list[dict[str, Any]]:
    """Load text/image pairs from the meme RAG source directory."""
    root = Path(source_dir or config.MEME_RAG_SOURCE_DIR)
    if not root.exists():
        raise FileNotFoundError(f"Meme RAG source directory not found: {root}")

    assets: list[dict[str, Any]] = []
    for doc_path in sorted(root.glob("*.txt")):
        asset_id = _asset_id_for_doc(doc_path)
        image_path = _find_image(root, asset_id)
        if image_path is None:
            logger.warning("Skipping meme doc with no matching image: %s", doc_path)
            continue

        doc_text = doc_path.read_text(encoding="utf-8").strip()
        if not doc_text:
            logger.warning("Skipping empty meme doc: %s", doc_path)
            continue

        assets.append(
            {
                "asset_id": asset_id,
                "title": _title(asset_id),
                "text": _text_for_asset(asset_id, doc_text),
                "source_text_path": str(doc_path),
                "source_image_path": str(image_path),
                "image_file": image_path.name,
            }
        )
    return assets


def build_meme_records(
    source_dir: str | Path | None = None,
    image_urls: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Build Pinecone integrated-embedding records for meme assets."""
    image_urls = image_urls or {}
    records: list[dict[str, Any]] = []
    for asset in load_meme_assets(source_dir):
        asset_id = str(asset["asset_id"])
        image_path = image_urls.get(asset_id) or str(asset["source_image_path"])
        records.append(
            {
                "_id": asset_id,
                "text": str(asset["text"]),
                "asset_id": asset_id,
                "title": str(asset["title"]),
                "image_path": image_path,
                "image_file": str(asset["image_file"]),
                "source": "meme_rag",
            }
        )
    return records


def clear_meme_namespace_sync() -> None:
    """Clear only the meme namespace, leaving product vectors untouched."""
    index = get_pinecone_index()
    try:
        index.delete(delete_all=True, namespace=config.PINECONE_MEME_NAMESPACE)
    except Exception as e:
        if "Namespace not found" not in str(e):
            raise
        logger.info(
            "Pinecone namespace %s does not exist yet",
            config.PINECONE_MEME_NAMESPACE,
        )
    logger.info("Cleared Pinecone namespace %s", config.PINECONE_MEME_NAMESPACE)


async def clear_meme_namespace() -> None:
    await asyncio.to_thread(clear_meme_namespace_sync)


def upsert_meme_records_sync(records: list[dict[str, Any]]) -> int:
    """Upsert meme records into the configured Pinecone meme namespace."""
    if not records:
        return 0
    index = get_pinecone_index()
    batch_size = 96
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        index.upsert_records(
            namespace=config.PINECONE_MEME_NAMESPACE,
            records=batch,
        )
        logger.info("Pinecone meme upsert batch: %d records", len(batch))
    return len(records)


async def upsert_meme_records(records: list[dict[str, Any]]) -> int:
    return await asyncio.to_thread(upsert_meme_records_sync, records)


def rebuild_meme_namespace_sync(
    source_dir: str | Path | None = None,
    image_urls: dict[str, str] | None = None,
    clear: bool = True,
) -> dict[str, Any]:
    records = build_meme_records(source_dir, image_urls=image_urls)
    if clear:
        clear_meme_namespace_sync()
    count = upsert_meme_records_sync(records)
    return {
        "namespace": config.PINECONE_MEME_NAMESPACE,
        "records": count,
        "cleared": clear,
    }


async def rebuild_meme_namespace(
    source_dir: str | Path | None = None,
    image_urls: dict[str, str] | None = None,
    clear: bool = True,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        rebuild_meme_namespace_sync,
        source_dir,
        image_urls,
        clear,
    )


def _normalise_hit(hit: Any) -> dict[str, Any]:
    if hasattr(hit, "model_dump"):
        hit = hit.model_dump()
    if isinstance(hit, dict):
        fields = hit.get("fields", {}) or {}
        score = hit.get("_score") or hit.get("score") or 0.0
        hit_id = hit.get("_id") or hit.get("id") or ""
    else:
        fields = getattr(hit, "fields", {}) or {}
        score = getattr(hit, "score", 0.0)
        hit_id = getattr(hit, "id", "")
    return {
        "asset_id": fields.get("asset_id") or hit_id,
        "title": fields.get("title", ""),
        "image_path": fields.get("image_path", ""),
        "image_file": fields.get("image_file", ""),
        "score": float(score or 0.0),
        "retrieval_method": "meme_pinecone",
    }


def search_memes_sync(
    query: str,
    top_k: int = 3,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Search meme assets by semantic text query."""
    if not query or not query.strip():
        return []
    index = get_pinecone_index()
    kwargs: dict[str, Any] = {
        "namespace": config.PINECONE_MEME_NAMESPACE,
        "top_k": top_k,
        "inputs": {"text": query},
        "fields": ["asset_id", "title", "image_path", "image_file", "source"],
    }
    if filters:
        kwargs["filter"] = filters

    result = index.search_records(**kwargs)
    hits = result.get("result", {}).get("hits", []) if isinstance(result, dict) else []
    if not hits and hasattr(result, "result"):
        hits = getattr(result.result, "hits", []) or []
    return [h for h in (_normalise_hit(hit) for hit in hits) if h.get("asset_id")]


async def search_memes(
    query: str,
    top_k: int = 3,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return await asyncio.to_thread(search_memes_sync, query, top_k, filters)


def _forced_asset_id(user_input: str) -> str | None:
    q = (user_input or "").strip().lower()
    if _GREETING_RE.match(q) or "say hi" in q:
        return "eager_hello_cat"
    if any(phrase in q for phrase in ["love you", "love u", "i love", "how are you", "how r u", "how is it going", "how's it going", "thank you", "thanks"]):
        return "eager_hello_cat"
    return None


async def select_meme_for_turn(
    user_input: str,
    assistant_text: str = "",
) -> dict[str, Any] | None:
    """Return the best meme for a turn, or None when no meme should be shown."""
    if not config.MEME_RAG_ENABLED:
        return None

    forced = _forced_asset_id(user_input)
    if forced:
        query = _FORCE_QUERIES.get(forced, forced)
        matches = await search_memes(
            query,
            top_k=1,
            filters={"asset_id": {"$eq": forced}},
        )
        return matches[0] if matches else None

    combined = f"{user_input}\n{assistant_text}".strip()
    if not _MEME_TRIGGER_RE.search(combined):
        return None

    query = (
        "Pick the best e-commerce chat reaction meme for this turn.\n"
        f"User message: {user_input}\n"
        f"Assistant response: {assistant_text}"
    )
    matches = await search_memes(query, top_k=1)
    if not matches:
        return None
    top = matches[0]
    if float(top.get("score") or 0.0) < config.MEME_RAG_MIN_SCORE:
        return None
    return top
