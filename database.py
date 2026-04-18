"""Supabase Postgres schema + database helpers.

The rest of the backend imports this module only; database credentials stay here
and in backend environment variables.
"""

import json
import datetime
import random
import logging
import re
import threading
from difflib import SequenceMatcher
from pathlib import Path

import psycopg2
import config

DB_PATH = Path(config.DB_PATH)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger(__name__)

_local = threading.local()


class Row:
    """Small row wrapper with sqlite.Row-style access by name or index."""

    def __init__(self, columns: list[str], values: tuple):
        self._columns = columns
        self._values = tuple(self._normalize(value) for value in values)
        self._data = dict(zip(columns, self._values))

    @staticmethod
    def _normalize(value):
        if isinstance(value, (datetime.datetime, datetime.date)):
            return value.isoformat()
        return value

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def keys(self):
        return self._data.keys()

    def items(self):
        return self._data.items()

    def values(self):
        return self._data.values()

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __repr__(self):
        return repr(self._data)


class QueryResult:
    def __init__(self, cursor):
        self._cursor = cursor
        self._columns = [d[0] for d in cursor.description] if cursor.description else []
        self.rowcount = cursor.rowcount
        if not self._columns:
            cursor.close()

    def fetchone(self):
        try:
            row = self._cursor.fetchone()
            return Row(self._columns, row) if row else None
        finally:
            self._cursor.close()

    def fetchall(self):
        try:
            return [Row(self._columns, row) for row in self._cursor.fetchall()]
        finally:
            self._cursor.close()


def _convert_placeholders(sql: str) -> str:
    return sql.replace("?", "%s")


class PostgresConnection:
    def __init__(self, raw):
        self.raw = raw

    @property
    def closed(self) -> bool:
        return bool(self.raw.closed)

    def execute(self, sql: str, params: tuple | list | None = None) -> QueryResult:
        cursor = self.raw.cursor()
        try:
            cursor.execute(_convert_placeholders(sql), params)
            return QueryResult(cursor)
        except Exception:
            cursor.close()
            self.raw.rollback()
            raise

    def executemany(self, sql: str, seq_of_params) -> QueryResult:
        cursor = self.raw.cursor()
        try:
            cursor.executemany(_convert_placeholders(sql), seq_of_params)
            return QueryResult(cursor)
        except Exception:
            cursor.close()
            self.raw.rollback()
            raise

    def executescript(self, script: str) -> None:
        cursor = self.raw.cursor()
        try:
            for statement in script.split(";"):
                statement = statement.strip()
                if statement:
                    cursor.execute(statement)
        except Exception:
            self.raw.rollback()
            raise
        finally:
            cursor.close()

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()


def _connect_raw():
    if not config.DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is required. Set it to the Supabase Postgres connection string "
            "in backend .env or Render environment variables."
        )
    return psycopg2.connect(
        config.DATABASE_URL,
        sslmode=config.DB_SSLMODE,
        connect_timeout=10,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    )


def get_conn() -> PostgresConnection:
    """Return a thread-local persistent Supabase Postgres connection."""
    conn = getattr(_local, "conn", None)
    if conn is None or conn.closed:
        conn = PostgresConnection(_connect_raw())
        _local.conn = conn
    return conn


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
}

_IMAGES = Path(config.PRODUCT_IMAGES_DIR)

_CATEGORIES = {
    "laptop": ("laptops", 0, 49999), "nitro": ("laptops", 0, 89999), "loq": ("laptops", 0, 69999),
    "latitude": ("laptops", 0, 45999), "speaker": ("electronics", 0, 3999),
    "soundbox": ("electronics", 0, 3499), "thunder": ("electronics", 0, 7999),
    "camera": ("electronics", 0, 2499), "cctv": ("electronics", 0, 2499),
    "bag": ("bags", 0, 999), "backpack": ("bags", 0, 1299),
    "sunglasses": ("accessories", 0, 599), "wayfarer": ("accessories", 0, 599),
    "kurti": ("kurti", 1, 1499), "kurta": ("kurti", 1, 1299),
    "jeans": ("jeans", 1, 1799), "denim": ("jeans", 1, 1799),
    "shirt": ("shirt", 1, 1299), "tshirt": ("tshirt", 1, 899), "tee": ("tshirt", 1, 799),
    "jacket": ("outerwear", 1, 2499), "dress": ("dress", 1, 1999),
}
_COLORS = ["red","blue","green","black","white","yellow","pink","purple",
           "orange","grey","gray","brown","navy","royal","maroon","beige"]


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

    return (name, category, color, float(price), name, random.randint(5, 20),
            str(image_path), tags, is_wearable)


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
        img for img in image_dir.iterdir()
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
    conn.execute("INSERT INTO sessions (id) VALUES ('demo') ON CONFLICT (id) DO NOTHING")
    rows = conn.execute("SELECT id, name, category, price FROM products LIMIT 20").fetchall()
    if not rows:
        return
    for _ in range(50):
        row = random.choice(rows)
        qty = random.randint(1, 3)
        days = random.randint(0, 60)
        ts = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
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
            logger.info("Seeded %d products from %s", len(seed_products), config.PRODUCT_IMAGES_DIR)
    _repair_product_image_paths(conn)
    if conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0:
        _seed_orders(conn)
        logger.info("Seeded 50 demo orders")
    conn.commit()
    _validate_schema(conn)
    logger.info("Database ready: Supabase Postgres")


def _validate_schema(conn: PostgresConnection) -> None:
    rows = conn.execute(
        "SELECT table_name AS name FROM information_schema.tables WHERE table_schema = 'public'"
    ).fetchall()
    tables = {row["name"] for row in rows}
    missing = sorted(_REQUIRED_TABLES - tables)
    if missing:
        raise RuntimeError(f"Database initialization missing tables: {missing}")


def startup() -> None:
    """Open and validate the Supabase Postgres database during FastAPI startup."""
    init_db()


# ── Session ─────────────────────────────────────────────────────────────────

def ensure_session(sid: str):
    if not sid or not sid.strip():
        raise ValueError("session_id is required")
    conn = get_conn()
    conn.execute("INSERT INTO sessions (id) VALUES (?) ON CONFLICT (id) DO NOTHING", (sid,))
    conn.execute("UPDATE sessions SET last_active=NOW() WHERE id=?", (sid,))
    conn.commit()


# ── Chat history ────────────────────────────────────────────────────────────

def save_message(sid: str, role: str, content: str, tool_name: str = None):
    ensure_session(sid)
    conn = get_conn()
    conn.execute(
        "INSERT INTO chat_history (session_id,role,content,tool_name) VALUES (?,?,?,?)",
        (sid, role, content, tool_name),
    )
    conn.commit()


def load_history(sid: str, limit: int = 20) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT role,content,tool_name,created_at as timestamp FROM chat_history WHERE session_id=? ORDER BY id DESC LIMIT ?",
        (sid, limit),
    ).fetchall()
    return [dict(r) for r in reversed(rows)]


def clear_history(sid: str):
    conn = get_conn()
    conn.execute("DELETE FROM chat_history WHERE session_id=?", (sid,))
    conn.commit()


# ── Cart ────────────────────────────────────────────────────────────────────

def db_add_to_cart(sid, product_name, price, quantity=1, product_id=None):
    ensure_session(sid)
    conn = get_conn()
    if product_id is None:
        prod = conn.execute(
            "SELECT id FROM products WHERE LOWER(name) = LOWER(?)", (product_name,)
        ).fetchone()
        if prod:
            product_id = prod["id"]
    row = conn.execute(
        "SELECT id,quantity FROM cart_items WHERE session_id=? AND product_name=?",
        (sid, product_name),
    ).fetchone()
    if row:
        conn.execute("UPDATE cart_items SET quantity=quantity+? WHERE id=?", (quantity, row["id"]))
    else:
        conn.execute(
            "INSERT INTO cart_items (session_id,product_id,product_name,price,quantity) VALUES (?,?,?,?,?)",
            (sid, product_id, product_name, price, quantity),
        )
    conn.commit()


def db_get_cart(sid: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT ci.id, ci.product_id, ci.product_name, ci.price, ci.quantity,
                  COALESCE(p1.image_path, p2.image_path) as image_path,
                  COALESCE(p1.color, p2.color) as color,
                  COALESCE(p1.category, p2.category) as category
           FROM cart_items ci
           LEFT JOIN products p1 ON p1.id = ci.product_id
           LEFT JOIN products p2 ON LOWER(p2.name) = LOWER(ci.product_name)
           WHERE ci.session_id=? ORDER BY ci.created_at""",
        (sid,),
    ).fetchall()
    return [dict(r) for r in rows]


def db_remove_from_cart(sid: str, product_name: str):
    conn = get_conn()
    conn.execute(
        "DELETE FROM cart_items WHERE session_id=? AND LOWER(product_name) = LOWER(?)",
        (sid, product_name),
    )
    conn.commit()


def db_clear_cart(sid: str):
    conn = get_conn()
    conn.execute("DELETE FROM cart_items WHERE session_id=?", (sid,))
    conn.commit()


def db_update_cart_quantity(sid: str, product_name: str, quantity: int):
    conn = get_conn()
    if quantity <= 0:
        conn.execute("DELETE FROM cart_items WHERE session_id=? AND product_name=?", (sid, product_name))
    else:
        conn.execute(
            "UPDATE cart_items SET quantity=? WHERE session_id=? AND product_name=?",
            (quantity, sid, product_name),
        )
    conn.commit()


def cart_totals(cart: list[dict]) -> tuple[int, float]:
    """Compute (item_count, total_price) from a cart items list."""
    count = sum(int(i.get("quantity", 0)) for i in cart)
    total = round(sum(float(i.get("price", 0)) * int(i.get("quantity", 0)) for i in cart), 2)
    return count, total


def cart_count(sid: str) -> int:
    cart = db_get_cart(sid)
    count, _ = cart_totals(cart)
    return count


def cart_total(sid: str) -> float:
    cart = db_get_cart(sid)
    _, total = cart_totals(cart)
    return total


def place_order(sid: str) -> list[int]:
    """Convert all cart items into orders and clear the cart. Returns list of order IDs."""
    cart = db_get_cart(sid)
    if not cart:
        return []
    conn = get_conn()
    order_ids = []
    for item in cart:
        cur = conn.execute(
            "INSERT INTO orders (session_id, product_id, product_name, category, price, quantity, status) "
            "VALUES (?, ?, ?, ?, ?, ?, 'pending') RETURNING id",
            (sid, item.get("product_id"), item["product_name"],
             item.get("category", ""), float(item["price"]), int(item["quantity"])),
        )
        order_ids.append(cur.fetchone()["id"])
    conn.execute("DELETE FROM cart_items WHERE session_id=?", (sid,))
    conn.commit()
    return order_ids


# ── Products (SQL keyword search — no vector store) ────────────────────────

def get_all_products() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM products ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def search_products(query: str, limit: int = 8) -> list[dict]:
    """Pure SQL keyword search with scoring. No embeddings needed."""
    tokens = [t.strip().lower() for t in query.split() if len(t.strip()) > 1]
    if not tokens:
        return get_all_products()[:limit]

    conn = get_conn()
    rows = conn.execute("SELECT * FROM products WHERE quantity > 0").fetchall()

    scored = []
    for row in rows:
        r = dict(row)
        score = 0.0
        name_l = r.get("name", "").lower()
        cat_l = r.get("category", "").lower()
        color_l = r.get("color", "").lower()
        desc_l = r.get("description", "").lower()
        tags_l = r.get("tags", "").lower()

        for tok in tokens:
            if tok in name_l:
                score += 5.0
            if tok in color_l:
                score += 4.0
            if tok in cat_l:
                score += 3.0
            if tok in tags_l:
                score += 2.0
            if tok in desc_l:
                score += 1.0

        if score > 0:
            r["_score"] = score
            scored.append(r)

    scored.sort(key=lambda x: x["_score"], reverse=True)
    for r in scored:
        r.pop("_score", None)
    return scored[:limit]


def get_product_by_name(name: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM products WHERE LOWER(name) LIKE LOWER(?) LIMIT 1",
        (f"%{name}%",),
    ).fetchone()
    return dict(row) if row else None


def get_product_by_id(pid: int) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    return dict(row) if row else None


def insert_product(name, category, color, price, description, quantity,
                   image_path="", tags="[]", is_wearable=0) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO products (name,category,color,price,description,quantity,image_path,tags,is_wearable) "
        "VALUES (?,?,?,?,?,?,?,?,?) RETURNING id",
        (name, category, color, price, description, quantity, image_path, tags, is_wearable),
    )
    pid = cur.fetchone()["id"]
    conn.commit()
    return pid


def update_product(pid: int, **kwargs):
    if not kwargs:
        return
    conn = get_conn()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [pid]
    conn.execute(f"UPDATE products SET {sets}, updated_at=NOW() WHERE id=?", vals)
    conn.commit()


def delete_product_row(pid: int) -> bool:
    conn = get_conn()
    cur = conn.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()
    return cur.rowcount > 0


# ── Analytics ───────────────────────────────────────────────────────────────

def get_summary_stats() -> dict:
    conn = get_conn()
    total_products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    total_revenue = conn.execute("SELECT COALESCE(SUM(price*quantity),0) FROM orders").fetchone()[0]
    total_customers = conn.execute("SELECT COUNT(DISTINCT session_id) FROM orders").fetchone()[0]
    return {
        "total_products": total_products,
        "total_orders": total_orders,
        "total_revenue": round(total_revenue, 2),
        "total_customers": total_customers,
    }


def get_revenue_by_day(days: int = 30) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT DATE(created_at) as date, SUM(price*quantity) as revenue, COUNT(*) as orders
           FROM orders WHERE created_at >= CURRENT_DATE + (?)::interval
           GROUP BY DATE(created_at) ORDER BY date""",
        (f"-{days} days",),
    ).fetchall()
    return [dict(r) for r in rows]


def get_top_products(limit: int = 5) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT product_name, SUM(quantity) as total_sold, SUM(price*quantity) as revenue
           FROM orders GROUP BY product_name ORDER BY total_sold DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_revenue_by_category() -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT COALESCE(category,'other') as category, SUM(price*quantity) as revenue
           FROM orders GROUP BY category ORDER BY revenue DESC""",
    ).fetchall()
    return [dict(r) for r in rows]


def get_stock_levels() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT id,name,category,quantity,price FROM products ORDER BY quantity ASC").fetchall()
    return [dict(r) for r in rows]


def get_recent_orders(limit: int = 10) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


# ── Order History (per session) ────────────────────────────────────────────

def get_orders_by_session(sid: str, limit: int = 50) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT o.id, o.product_name, o.category, o.price, o.quantity, o.status, o.created_at,
                  COALESCE(p.image_path, '') as image_path
           FROM orders o
           LEFT JOIN products p ON p.id = o.product_id
           WHERE o.session_id = ?
           ORDER BY o.created_at DESC LIMIT ?""",
        (sid, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_order_stats_by_session(sid: str) -> dict:
    conn = get_conn()
    row = conn.execute(
        """SELECT COUNT(*) as total_orders, COALESCE(SUM(price * quantity), 0) as total_spent
           FROM orders WHERE session_id = ?""",
        (sid,),
    ).fetchone()
    return dict(row) if row else {"total_orders": 0, "total_spent": 0}


# ── Wishlist ────────────────────────────────────────────────────────────────

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


# ── Try-on image helpers ────────────────────────────────────────────────────

def save_user_image(file_bytes: bytes, session_id: str, ext: str = ".jpg") -> str:
    out = Path(config.USER_UPLOADS_DIR) / f"{session_id}{ext}"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(file_bytes)
    return str(out)


def save_product_image(file_bytes: bytes, product_name: str, ext: str = ".jpg") -> str:
    safe_name = product_name.lower().replace(" ", "_").replace("/", "_")
    out = Path(config.PRODUCT_IMAGES_DIR) / f"{safe_name}{ext}"
    counter = 1
    while out.exists():
        out = Path(config.PRODUCT_IMAGES_DIR) / f"{safe_name}_{counter}{ext}"
        counter += 1
    out.write_bytes(file_bytes)
    return str(out)


# ── Users / Auth ────────────────────────────────────────────────────────────

def upsert_user(name: str, email: str) -> dict:
    """Insert or update a user by email. Returns the full user row."""
    conn = get_conn()
    conn.execute(
        """INSERT INTO users (name, email) VALUES (?, ?)
           ON CONFLICT(email) DO UPDATE SET
             name = excluded.name,
             last_seen = CURRENT_TIMESTAMP""",
        (name.strip(), email.strip().lower()),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id, name, email FROM users WHERE email = ?",
        (email.strip().lower(),),
    ).fetchone()
    return dict(row) if row else {}


def bind_session_user(session_id: str, user_id: int) -> None:
    ensure_session(session_id)
    conn = get_conn()
    conn.execute(
        "UPDATE sessions SET user_id = ?, last_active = CURRENT_TIMESTAMP WHERE id = ?",
        (user_id, session_id),
    )
    # Backfill any existing orders/cart with the new user_id
    conn.execute("UPDATE orders SET user_id = ? WHERE session_id = ? AND user_id IS NULL", (user_id, session_id))
    conn.execute("UPDATE cart_items SET user_id = ? WHERE session_id = ? AND user_id IS NULL", (user_id, session_id))
    conn.commit()


def unbind_session_user(session_id: str) -> None:
    conn = get_conn()
    conn.execute("UPDATE sessions SET user_id = NULL WHERE id = ?", (session_id,))
    conn.commit()


def get_user_by_session(session_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        """SELECT u.id, u.name, u.email FROM sessions s
           JOIN users u ON u.id = s.user_id
           WHERE s.id = ?""",
        (session_id,),
    ).fetchone()
    return dict(row) if row else None


# ── Product view tracking ──────────────────────────────────────────────────

def log_product_view(session_id: str, product_id: int, search_query: str | None = None) -> None:
    ensure_session(session_id)
    conn = get_conn()
    conn.execute(
        "INSERT INTO product_views (session_id, product_id, search_query) VALUES (?, ?, ?)",
        (session_id, product_id, search_query),
    )
    conn.commit()


# ── Orders: status update + logistics view ────────────────────────────────

_ALLOWED_STATUSES = {"processing", "shipped", "in_transit"}


def update_order_status(order_id: int, status: str) -> bool:
    if status not in _ALLOWED_STATUSES:
        raise ValueError(f"status must be one of {sorted(_ALLOWED_STATUSES)}")
    conn = get_conn()
    cur = conn.execute(
        "UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, order_id),
    )
    conn.commit()
    return cur.rowcount > 0


def get_logistics_rows(limit: int = 20) -> list[dict]:
    """Recent orders joined with users, ready for the Active Logistics table."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT o.id AS order_id,
                  o.product_name,
                  o.quantity,
                  (o.price * o.quantity) AS revenue,
                  o.status,
                  o.created_at,
                  COALESCE(u.name, 'Guest') AS user_name,
                  COALESCE(u.email, '') AS user_email
           FROM orders o
           LEFT JOIN users u ON u.id = o.user_id
           ORDER BY o.created_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


# ── Daily signals for ML forecasting ───────────────────────────────────────

def get_daily_signals(days: int = 90) -> list[dict]:
    """Per-day combined signals: orders revenue/units, cart adds, product views."""
    conn = get_conn()
    since = f"-{days} days"
    rows = conn.execute(
        """WITH o AS (
             SELECT DATE(created_at) AS date,
                    SUM(price*quantity) AS revenue,
                    SUM(quantity) AS units
             FROM orders WHERE created_at >= CURRENT_DATE + (?)::interval
             GROUP BY DATE(created_at)
           ),
           c AS (
             SELECT DATE(created_at) AS date, COUNT(*) AS cart_adds
             FROM cart_items WHERE created_at >= CURRENT_DATE + (?)::interval
             GROUP BY DATE(created_at)
           ),
           v AS (
             SELECT DATE(viewed_at) AS date, COUNT(*) AS views
             FROM product_views WHERE viewed_at >= CURRENT_DATE + (?)::interval
             GROUP BY DATE(viewed_at)
           )
           SELECT DISTINCT date FROM (
             SELECT date FROM o UNION SELECT date FROM c UNION SELECT date FROM v
           ) WHERE date IS NOT NULL ORDER BY date""",
        (since, since, since),
    ).fetchall()
    dates = [r["date"] for r in rows]
    if not dates:
        return []

    rev_map = {
        r["date"]: dict(r)
        for r in conn.execute(
            """SELECT DATE(created_at) AS date,
                      SUM(price*quantity) AS revenue,
                      SUM(quantity) AS units
               FROM orders WHERE created_at >= CURRENT_DATE + (?)::interval
               GROUP BY DATE(created_at)""",
            (since,),
        ).fetchall()
    }
    cart_map = {
        r["date"]: r["cart_adds"]
        for r in conn.execute(
            """SELECT DATE(created_at) AS date, COUNT(*) AS cart_adds
               FROM cart_items WHERE created_at >= CURRENT_DATE + (?)::interval
               GROUP BY DATE(created_at)""",
            (since,),
        ).fetchall()
    }
    view_map = {
        r["date"]: r["views"]
        for r in conn.execute(
            """SELECT DATE(viewed_at) AS date, COUNT(*) AS views
               FROM product_views WHERE viewed_at >= CURRENT_DATE + (?)::interval
               GROUP BY DATE(viewed_at)""",
            (since,),
        ).fetchall()
    }

    out = []
    for d in dates:
        o = rev_map.get(d, {})
        out.append({
            "date": d,
            "revenue": float(o.get("revenue") or 0),
            "units": int(o.get("units") or 0),
            "cart_adds": int(cart_map.get(d, 0)),
            "views": int(view_map.get(d, 0)),
        })
    return out


def get_product_signals(days: int = 30) -> list[dict]:
    """Per-product signals over the last N days for Trending Collections."""
    conn = get_conn()
    since = f"-{days} days"
    rows = conn.execute(
        """SELECT p.id AS product_id,
                  p.name, p.category, p.price, p.image_path,
                  COALESCE(SUM(o.quantity), 0) AS orders_units,
                  COALESCE((SELECT COUNT(*) FROM cart_items c
                            WHERE c.product_id = p.id
                              AND c.created_at >= CURRENT_DATE + (?)::interval), 0) AS cart_adds,
                  COALESCE((SELECT COUNT(*) FROM product_views v
                            WHERE v.product_id = p.id
                              AND v.viewed_at >= CURRENT_DATE + (?)::interval), 0) AS views
           FROM products p
           LEFT JOIN orders o
             ON o.product_id = p.id AND o.created_at >= CURRENT_DATE + (?)::interval
           GROUP BY p.id""",
        (since, since, since),
    ).fetchall()
    return [dict(r) for r in rows]


def get_customer_count() -> int:
    """Distinct customers = users rows + guest sessions that placed orders."""
    conn = get_conn()
    users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    guests = conn.execute(
        "SELECT COUNT(DISTINCT session_id) FROM orders WHERE user_id IS NULL"
    ).fetchone()[0]
    return int(users) + int(guests)


def get_revenue_for_day(days_ago: int = 0) -> float:
    conn = get_conn()
    row = conn.execute(
        """SELECT COALESCE(SUM(price*quantity), 0) AS rev FROM orders
           WHERE DATE(created_at) = (CURRENT_DATE + (?)::interval)::date""",
        (f"-{days_ago} days",),
    ).fetchone()
    return float(row["rev"] or 0)
