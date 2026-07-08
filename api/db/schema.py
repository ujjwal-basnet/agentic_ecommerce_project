"""Schema bootstrap and seed data."""

from __future__ import annotations

import datetime
import json
import logging
import random
import re
from difflib import SequenceMatcher
from pathlib import Path

from api import config
from api.db.knowledge import _seed_knowledge_base
from api.db.pool import PostgresConnection, get_conn

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id          SERIAL PRIMARY KEY,
    name        TEXT    NOT NULL,
    category    TEXT,
    color       TEXT,
    price       DOUBLE PRECISION NOT NULL DEFAULT 0,
    description TEXT,
    quantity    INTEGER NOT NULL DEFAULT 0,
    image_path  TEXT,
    tags        TEXT    DEFAULT '[]',
    is_wearable INTEGER DEFAULT 0,
    indexed     INTEGER DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    name        TEXT,
    email       TEXT UNIQUE,
    phone       TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    last_seen   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sessions (
    id               TEXT PRIMARY KEY,
    user_id          INTEGER REFERENCES users(id) ON DELETE SET NULL,
    user_agent       TEXT,
    discount_applied INTEGER DEFAULT 0,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    last_active      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS chat_history (
    id          SERIAL PRIMARY KEY,
    session_id  TEXT    NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role        TEXT    NOT NULL,
    content     TEXT    NOT NULL,
    tool_name   TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_history(session_id, created_at);

CREATE TABLE IF NOT EXISTS cart_items (
    id           SERIAL PRIMARY KEY,
    session_id   TEXT    NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    user_id      INTEGER REFERENCES users(id) ON DELETE SET NULL,
    product_id   INTEGER REFERENCES products(id) ON DELETE SET NULL,
    product_name TEXT    NOT NULL,
    price        DOUBLE PRECISION NOT NULL,
    quantity     INTEGER NOT NULL DEFAULT 1,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cart_session ON cart_items(session_id);
CREATE INDEX IF NOT EXISTS idx_cart_user ON cart_items(user_id);
CREATE INDEX IF NOT EXISTS idx_cart_product ON cart_items(product_id);

CREATE TABLE IF NOT EXISTS wishlists (
    id          SERIAL PRIMARY KEY,
    session_id  TEXT    NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(session_id, product_id)
);
CREATE INDEX IF NOT EXISTS idx_wishlists_user ON wishlists(user_id);
CREATE INDEX IF NOT EXISTS idx_wishlists_product ON wishlists(product_id);

CREATE TABLE IF NOT EXISTS orders (
    id               SERIAL PRIMARY KEY,
    session_id       TEXT    REFERENCES sessions(id) ON DELETE SET NULL,
    user_id          INTEGER REFERENCES users(id) ON DELETE SET NULL,
    product_id       INTEGER REFERENCES products(id) ON DELETE SET NULL,
    product_name     TEXT    NOT NULL,
    category         TEXT,
    price            DOUBLE PRECISION NOT NULL,
    quantity         INTEGER NOT NULL DEFAULT 1,
    status           TEXT    NOT NULL DEFAULT 'pending',
    shipping_name    TEXT,
    shipping_phone   TEXT,
    shipping_address TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_orders_session ON orders(session_id);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_product ON orders(product_id);

CREATE TABLE IF NOT EXISTS product_views (
    id           SERIAL PRIMARY KEY,
    session_id   TEXT    REFERENCES sessions(id) ON DELETE SET NULL,
    product_id   INTEGER REFERENCES products(id) ON DELETE CASCADE,
    search_query TEXT,
    viewed_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_views_product ON product_views(product_id);
CREATE INDEX IF NOT EXISTS idx_views_session ON product_views(session_id);
CREATE INDEX IF NOT EXISTS idx_views_viewed_at ON product_views(viewed_at);

CREATE TABLE IF NOT EXISTS knowledge_base (
    id       SERIAL PRIMARY KEY,
    title    TEXT NOT NULL,
    category TEXT NOT NULL,
    content  TEXT NOT NULL
);
"""

_REQUIRED_TABLES = {
    "products",
    "users",
    "sessions",
    "chat_history",
    "cart_items",
    "wishlists",
    "orders",
    "product_views",
    "knowledge_base",
}

_IMAGES = Path(config.PRODUCT_IMAGES_DIR)

_CATEGORIES = {
    "laptop": ("laptops", 0, 49999),
    "nitro": ("laptops", 0, 89999),
    "loq": ("laptops", 0, 69999),
    "latitude": ("laptops", 0, 45999),
    "speaker": ("electronics", 0, 3999),
    "soundbox": ("electronics", 0, 3499),
    "thunder": ("electronics", 0, 7999),
    "camera": ("electronics", 0, 2499),
    "cctv": ("electronics", 0, 2499),
    "bag": ("bags", 0, 999),
    "backpack": ("bags", 0, 1299),
    "sunglasses": ("accessories", 0, 599),
    "wayfarer": ("accessories", 0, 599),
    "kurti": ("kurti", 1, 1499),
    "kurta": ("kurti", 1, 1299),
    "jeans": ("jeans", 1, 1799),
    "denim": ("jeans", 1, 1799),
    "shirt": ("shirt", 1, 1299),
    "tshirt": ("tshirt", 1, 899),
    "tee": ("tshirt", 1, 799),
    "jacket": ("outerwear", 1, 2499),
    "dress": ("dress", 1, 1999),
}

_COLORS = [
    "red",
    "blue",
    "green",
    "black",
    "white",
    "yellow",
    "pink",
    "purple",
    "orange",
    "grey",
    "gray",
    "brown",
    "navy",
    "royal",
    "maroon",
    "beige",
]


def _image_match_key(value: str) -> str:
    value = value.lower().replace("flavoured", "flavored")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _filename_to_product(image_path: Path) -> tuple:
    stem = image_path.stem.replace(".jpg", "")
    tokens = stem.replace("_", " ").replace("-", " ").lower().split()
    name = " ".join(w.capitalize() for w in tokens)

    category, is_wearable, price = "general", 0, 999
    for tok in tokens:
        if tok in _CATEGORIES:
            category, is_wearable, price = _CATEGORIES[tok]
            break

    color = next((t for t in tokens if t in _COLORS), "black")
    tags = json.dumps(list(dict.fromkeys(tokens)))  # preserve order, dedupe

    return (
        name,
        category,
        color,
        float(price),
        name,
        random.randint(5, 20),
        str(image_path),
        tags,
        is_wearable,
    )


def _build_seed_products() -> list[tuple]:
    """Scan PRODUCT_IMAGES_DIR and return a seed row for every image found."""
    products = []
    image_dir = Path(config.PRODUCT_IMAGES_DIR)
    if not image_dir.exists():
        return products
    for img in sorted(image_dir.iterdir()):
        if img.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".avif"):
            products.append(_filename_to_product(img))
    return products


def _repair_product_image_paths(conn: PostgresConnection) -> int:
    """Backfill missing image_path values from matching files in PRODUCT_IMAGES_DIR."""
    image_dir = Path(config.PRODUCT_IMAGES_DIR)
    if not image_dir.exists():
        return 0

    images = [
        img
        for img in image_dir.iterdir()
        if img.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".avif")
    ]
    if not images:
        return 0

    image_keys = [(_image_match_key(img.stem), img) for img in images]
    rows = conn.execute(
        "SELECT id, name FROM products WHERE image_path IS NULL OR image_path = ''"
    ).fetchall()

    repaired = 0
    for row in rows:
        product_key = _image_match_key(row["name"])
        best_score, best_image = max(
            (
                (SequenceMatcher(None, product_key, image_key).ratio(), img)
                for image_key, img in image_keys
            ),
            default=(0.0, None),
        )
        if best_image is not None and best_score >= 0.78:
            conn.execute(
                "UPDATE products SET image_path=?, updated_at=NOW() WHERE id=?",
                (str(best_image), row["id"]),
            )
            repaired += 1

    if repaired:
        logger.info("Repaired image_path for %d products", repaired)
    return repaired


def _seed_orders(conn):
    conn.execute(
        "INSERT INTO sessions (id) VALUES ('demo') ON CONFLICT (id) DO NOTHING"
    )
    rows = conn.execute(
        "SELECT id, name, category, price FROM products LIMIT 20"
    ).fetchall()
    if not rows:
        return
    for _ in range(50):
        row = random.choice(rows)
        qty = random.randint(1, 3)
        days = random.randint(0, 60)
        ts = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        conn.execute(
            "INSERT INTO orders (session_id,product_id,product_name,category,price,quantity,status,created_at) "
            "VALUES ('demo',?,?,?,?,?,'delivered',?)",
            (row["id"], row["name"], row["category"], row["price"], qty, ts),
        )


def init_db():
    conn = get_conn()
    conn.executescript(_SCHEMA)
    conn.commit()
    if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        seed_products = _build_seed_products()
        if seed_products:
            conn.executemany(
                "INSERT INTO products (name,category,color,price,description,quantity,image_path,tags,is_wearable) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                seed_products,
            )
            logger.info(
                "Seeded %d products from %s",
                len(seed_products),
                config.PRODUCT_IMAGES_DIR,
            )
    _repair_product_image_paths(conn)
    if conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0:
        _seed_orders(conn)
        logger.info("Seeded 50 demo orders")
    conn.commit()
    _seed_knowledge_base(conn)
    _validate_schema(conn)
    logger.info("Database ready: Supabase Postgres")


def _validate_schema(conn: PostgresConnection) -> None:
    schema = conn.execute("SELECT current_schema() AS schema").fetchone()["schema"]
    rows = conn.execute(
        "SELECT table_name AS name FROM information_schema.tables WHERE table_schema = ?",
        (schema,),
    ).fetchall()
    tables = {row["name"] for row in rows}
    missing = sorted(_REQUIRED_TABLES - tables)
    if missing:
        raise RuntimeError(
            f"Database initialization missing tables in schema {schema}: {missing}"
        )


def startup() -> None:
    """Open and validate the Supabase Postgres database during FastAPI startup."""
    init_db()
