"""Product CRUD, product cache, wishlist, and image helpers."""

from __future__ import annotations

import re
import threading as _threading
from pathlib import Path

from api import config
from api.db.pool import get_conn
from api.db.users import ensure_session
from api.integrations import storage


_products_cache: list[dict] | None = None
_products_cache_lock = _threading.Lock()


def _invalidate_products_cache() -> None:
    global _products_cache
    with _products_cache_lock:
        _products_cache = None


def get_all_products() -> list[dict]:
    global _products_cache
    cached = _products_cache
    if cached is not None:
        return cached
    conn = get_conn()
    rows = conn.execute("SELECT * FROM products ORDER BY id").fetchall()
    result = [dict(r) for r in rows]
    with _products_cache_lock:
        _products_cache = result
    return result


def search_products(query: str, limit: int = 8) -> list[dict]:
    """Postgres full-text search with ts_rank scoring, ILIKE fallback."""
    tokens = [
        re.sub(r"[^a-z0-9]", "", t.lower()) for t in query.split() if len(t.strip()) > 1
    ]
    tokens = [t for t in tokens if t]
    if not tokens:
        return get_all_products()[:limit]

    conn = get_conn()
    tsquery_str = " | ".join(tokens)
    doc_expr = (
        "to_tsvector('simple', COALESCE(name,'') || ' ' || COALESCE(category,'') || ' ' "
        "|| COALESCE(color,'') || ' ' || COALESCE(description,'') || ' ' || COALESCE(tags,''))"
    )
    rows = conn.execute(
        f"SELECT *, ts_rank({doc_expr}, to_tsquery('simple', ?)) AS _rank "
        f"FROM products WHERE quantity > 0 AND {doc_expr} @@ to_tsquery('simple', ?) "
        f"ORDER BY _rank DESC LIMIT ?",
        (tsquery_str, tsquery_str, limit),
    ).fetchall()

    if rows:
        return [dict(r) for r in rows]

    # Fallback: ILIKE for partial / substring matches
    like_clauses = []
    like_params = []
    for tok in tokens:
        pattern = f"%{tok}%"
        like_clauses.append(
            "(LOWER(name) LIKE ? OR LOWER(category) LIKE ? OR "
            "LOWER(color) LIKE ? OR LOWER(tags) LIKE ?)"
        )
        like_params.extend([pattern, pattern, pattern, pattern])
    where = " OR ".join(like_clauses)
    rows = conn.execute(
        f"SELECT * FROM products WHERE quantity > 0 AND ({where}) LIMIT ?",
        (*like_params, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_product_by_name(name: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM products WHERE LOWER(name) LIKE LOWER(?) LIMIT 1",
        (f"%{name}%",),
    ).fetchone()
    return dict(row) if row else None


def get_products_by_ids(ids: list[int]) -> list[dict]:
    """In-memory lookup from cached catalog — zero DB round-trips.
    Cache invalidates on any insert/update/delete."""
    if not ids:
        return []
    wanted = {int(i) for i in ids}
    return [p for p in get_all_products() if p.get("id") in wanted]


def get_product_by_id(pid: int) -> dict | None:
    """In-memory lookup from cached catalog — zero DB round-trips."""
    pid = int(pid)
    for p in get_all_products():
        if p.get("id") == pid:
            return p
    return None


def insert_product(
    name,
    category,
    color,
    price,
    description,
    quantity,
    image_path="",
    tags="[]",
    is_wearable=0,
) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO products (name,category,color,price,description,quantity,image_path,tags,is_wearable) "
        "VALUES (?,?,?,?,?,?,?,?,?) RETURNING id",
        (
            name,
            category,
            color,
            price,
            description,
            quantity,
            image_path,
            tags,
            is_wearable,
        ),
    )
    pid = cur.fetchone()["id"]
    conn.commit()
    _invalidate_products_cache()
    return pid


def update_product(pid: int, **kwargs):
    if not kwargs:
        return
    conn = get_conn()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [pid]
    conn.execute(f"UPDATE products SET {sets}, updated_at=NOW() WHERE id=?", vals)
    conn.commit()
    _invalidate_products_cache()


def delete_product_row(pid: int) -> bool:
    conn = get_conn()
    cur = conn.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()
    _invalidate_products_cache()
    return cur.rowcount > 0


def add_to_wishlist(sid: str, product_id: int):
    ensure_session(sid)
    conn = get_conn()
    conn.execute(
        "INSERT INTO wishlists (session_id,product_id) VALUES (?,?) ON CONFLICT (session_id, product_id) DO NOTHING",
        (sid, product_id),
    )
    conn.commit()


def get_wishlist(sid: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT w.product_id, p.name, p.price, p.image_path
           FROM wishlists w JOIN products p ON p.id=w.product_id
           WHERE w.session_id=?""",
        (sid,),
    ).fetchall()
    return [dict(r) for r in rows]


def save_user_image(file_bytes: bytes, session_id: str, ext: str = ".jpg") -> str:
    from api.integrations import storage

    ct = "image/jpeg" if ext.lower() in (".jpg", ".jpeg") else "image/png"
    url = storage.upload(
        "user-uploads", f"{session_id}{ext}", file_bytes, content_type=ct
    )
    if url:
        return url
    out = Path(config.USER_UPLOADS_DIR) / f"{session_id}{ext}"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(file_bytes)
    return str(out)


def save_product_image(file_bytes: bytes, product_name: str, ext: str = ".jpg") -> str:
    from api.integrations import storage

    safe_name = product_name.lower().replace(" ", "_").replace("/", "_")
    fname = f"{safe_name}{ext}"
    ct = "image/jpeg" if ext.lower() in (".jpg", ".jpeg") else "image/png"
    url = storage.upload("product-images", fname, file_bytes, content_type=ct)
    if url:
        return url
    out = Path(config.PRODUCT_IMAGES_DIR) / fname
    counter = 1
    while out.exists():
        out = Path(config.PRODUCT_IMAGES_DIR) / f"{safe_name}_{counter}{ext}"
        counter += 1
    out.write_bytes(file_bytes)
    return str(out)
