"""SQLite schema + ALL database helpers. Single source of truth for every DB call."""

import json
import sqlite3
import datetime
import random
import logging
import threading
from pathlib import Path
import config

DB_PATH = Path(config.DB_PATH)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger(__name__)

_local = threading.local()


def get_conn() -> sqlite3.Connection:
    """Return a thread-local persistent connection."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


_SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    category    TEXT,
    color       TEXT,
    price       REAL    NOT NULL DEFAULT 0,
    description TEXT,
    quantity    INTEGER NOT NULL DEFAULT 0,
    image_path  TEXT,
    tags        TEXT    DEFAULT '[]',
    is_wearable INTEGER DEFAULT 0,
    indexed     INTEGER DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT,
    email       TEXT UNIQUE,
    phone       TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    id               TEXT PRIMARY KEY,
    user_id          INTEGER REFERENCES users(id) ON DELETE SET NULL,
    user_agent       TEXT,
    discount_applied INTEGER DEFAULT 0,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role        TEXT    NOT NULL,
    content     TEXT    NOT NULL,
    tool_name   TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_history(session_id, created_at);

CREATE TABLE IF NOT EXISTS cart_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT    NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    user_id      INTEGER REFERENCES users(id) ON DELETE SET NULL,
    product_id   INTEGER REFERENCES products(id) ON DELETE SET NULL,
    product_name TEXT    NOT NULL,
    price        REAL    NOT NULL,
    quantity     INTEGER NOT NULL DEFAULT 1,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_cart_session ON cart_items(session_id);

CREATE TABLE IF NOT EXISTS wishlists (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, product_id)
);

CREATE TABLE IF NOT EXISTS orders (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id       TEXT    REFERENCES sessions(id) ON DELETE SET NULL,
    user_id          INTEGER REFERENCES users(id) ON DELETE SET NULL,
    product_id       INTEGER REFERENCES products(id) ON DELETE SET NULL,
    product_name     TEXT    NOT NULL,
    category         TEXT,
    price            REAL    NOT NULL,
    quantity         INTEGER NOT NULL DEFAULT 1,
    status           TEXT    NOT NULL DEFAULT 'pending',
    shipping_name    TEXT,
    shipping_phone   TEXT,
    shipping_address TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_orders_session ON orders(session_id);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);

CREATE TABLE IF NOT EXISTS product_views (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT    REFERENCES sessions(id) ON DELETE SET NULL,
    product_id   INTEGER REFERENCES products(id) ON DELETE CASCADE,
    search_query TEXT,
    viewed_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_views_product ON product_views(product_id);
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


def _seed_orders(conn):
    conn.execute("INSERT OR IGNORE INTO sessions (id) VALUES ('demo')")
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
    cols = [r[1] for r in conn.execute("PRAGMA table_info(products)").fetchall()]
    if "is_wearable" not in cols:
        conn.execute("ALTER TABLE products ADD COLUMN is_wearable INTEGER DEFAULT 0")
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
    if conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0:
        _seed_orders(conn)
        logger.info("Seeded 50 demo orders")
    conn.commit()
    _validate_schema(conn)
    logger.info("Database ready: %s", DB_PATH)


def _validate_schema(conn: sqlite3.Connection) -> None:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    tables = {row["name"] for row in rows}
    missing = sorted(_REQUIRED_TABLES - tables)
    if missing:
        raise RuntimeError(f"Database initialization missing tables: {missing}")


def startup() -> None:
    """Open and validate the SQLite database during FastAPI startup."""
    init_db()


# ── Session ─────────────────────────────────────────────────────────────────

def ensure_session(sid: str):
    if not sid or not sid.strip():
        raise ValueError("session_id is required")
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO sessions (id) VALUES (?)", (sid,))
    conn.execute("UPDATE sessions SET last_active=CURRENT_TIMESTAMP WHERE id=?", (sid,))
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
            "VALUES (?, ?, ?, ?, ?, ?, 'pending')",
            (sid, item.get("product_id"), item["product_name"],
             item.get("category", ""), float(item["price"]), int(item["quantity"])),
        )
        order_ids.append(cur.lastrowid)
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
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (name, category, color, price, description, quantity, image_path, tags, is_wearable),
    )
    conn.commit()
    pid = cur.lastrowid
    return pid


def update_product(pid: int, **kwargs):
    conn = get_conn()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [pid]
    conn.execute(f"UPDATE products SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE id=?", vals)
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
           FROM orders WHERE created_at >= DATE('now', ?) GROUP BY DATE(created_at) ORDER BY date""",
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
        "INSERT OR IGNORE INTO wishlists (session_id,product_id) VALUES (?,?)",
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
