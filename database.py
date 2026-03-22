"""SQLite schema + ALL database helpers. Single source of truth for every DB call."""

import json
import sqlite3
import datetime
import random
from pathlib import Path
import config

DB_PATH = Path(config.DB_PATH)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
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

_IMAGES = Path(config.DB_IMAGES_DIR)

_SEED_PRODUCTS = [
    ("Red T-Shirt", "tshirt", "red", 20.00, "Classic red cotton crew-neck t-shirt.", 15,
     str(_IMAGES / "red_tshirt.jpg"), '["red","tshirt","cotton","casual"]', 1),
    ("Blue T-Shirt", "tshirt", "blue", 22.00, "Navy blue regular-fit cotton t-shirt.", 12,
     str(_IMAGES / "blue_tshirt.jpeg"), '["blue","navy","tshirt","cotton"]', 1),
    ("Black T-Shirt", "tshirt", "black", 25.00, "Black casual t-shirt for everyday wear.", 6,
     str(_IMAGES / "black-tshirtfdas.jpg"), '["black","tshirt","casual"]', 1),
    ("Black Midi Dress", "dress", "black", 75.00, "Sleek black midi dress for evenings.", 6,
     str(_IMAGES / "dress_black.png"), '["black","dress","midi","evening"]', 1),
    ("Denim Jacket", "jacket", "blue", 90.00, "Classic blue denim jacket, slim fit.", 4,
     str(_IMAGES / "jacket_denim.png"), '["blue","denim","jacket","outerwear"]', 1),
    ("Sunglasses", "accessories", "black", 25.00, "Stylish black sunglasses.", 20,
     str(_IMAGES / "sunnglasses.avif"), '["black","sunglasses","accessories"]', 0),
    ("Red Saree", "sari", "red", 1500.00, "Traditional red silk saree for weddings.", 8,
     str(_IMAGES / "red_saree.jpg"), '["red","saree","sari","silk","wedding"]', 1),
    ("Blue Saree", "sari", "blue", 1800.00, "Royal blue chiffon saree.", 5,
     str(_IMAGES / "blue_saree.jpg"), '["blue","saree","sari","chiffon"]', 1),
    ("Black Kurta", "kurti", "black", 45.00, "Black cotton kurta for men.", 10,
     str(_IMAGES / "black_kurta.jpg"), '["black","kurta","kurti","cotton","ethnic"]', 1),
    ("White Dress", "dress", "white", 65.00, "Elegant white summer dress.", 7,
     str(_IMAGES / "white_dress.jpg"), '["white","dress","summer","elegant"]', 1),
]


def _seed_orders(conn):
    conn.execute("INSERT OR IGNORE INTO sessions (id) VALUES ('demo')")
    items = [
        (1, "Red T-Shirt", "tshirt", 20.0),
        (2, "Blue T-Shirt", "tshirt", 22.0),
        (3, "Black T-Shirt", "tshirt", 25.0),
        (4, "Black Midi Dress", "dress", 75.0),
        (5, "Denim Jacket", "jacket", 90.0),
        (6, "Sunglasses", "accessories", 25.0),
    ]
    for _ in range(50):
        pid, pname, cat, price = random.choice(items)
        qty = random.randint(1, 3)
        days = random.randint(0, 60)
        ts = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO orders (session_id,product_id,product_name,category,price,quantity,status,created_at) "
            "VALUES ('demo',?,?,?,?,?,'delivered',?)",
            (pid, pname, cat, price, qty, ts),
        )


def init_db():
    conn = get_conn()
    conn.executescript(_SCHEMA)
    conn.commit()
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(products)").fetchall()]
        if "is_wearable" not in cols:
            conn.execute("ALTER TABLE products ADD COLUMN is_wearable INTEGER DEFAULT 0")
            conn.commit()
    except Exception:
        pass
    if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO products (name,category,color,price,description,quantity,image_path,tags,is_wearable) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            _SEED_PRODUCTS,
        )
        print(f"[db] Seeded {len(_SEED_PRODUCTS)} products.")
    if conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0:
        _seed_orders(conn)
        print("[db] Seeded 50 demo orders.")
    conn.commit()
    conn.close()
    print(f"[db] Ready → {DB_PATH}")


# ── Session ─────────────────────────────────────────────────────────────────

def ensure_session(sid: str):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO sessions (id) VALUES (?)", (sid,))
    conn.execute("UPDATE sessions SET last_active=CURRENT_TIMESTAMP WHERE id=?", (sid,))
    conn.commit()
    conn.close()


# ── Chat history ────────────────────────────────────────────────────────────

def save_message(sid: str, role: str, content: str, tool_name: str = None):
    ensure_session(sid)
    conn = get_conn()
    conn.execute(
        "INSERT INTO chat_history (session_id,role,content,tool_name) VALUES (?,?,?,?)",
        (sid, role, content, tool_name),
    )
    conn.commit()
    conn.close()


def load_history(sid: str, limit: int = 20) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT role,content,tool_name FROM chat_history WHERE session_id=? ORDER BY id DESC LIMIT ?",
        (sid, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def clear_history(sid: str):
    conn = get_conn()
    conn.execute("DELETE FROM chat_history WHERE session_id=?", (sid,))
    conn.commit()
    conn.close()


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
    conn.close()


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
    conn.close()
    return [dict(r) for r in rows]


def db_remove_from_cart(sid: str, product_name: str):
    conn = get_conn()
    conn.execute(
        "DELETE FROM cart_items WHERE session_id=? AND LOWER(product_name) LIKE LOWER(?)",
        (sid, f"%{product_name}%"),
    )
    conn.commit()
    conn.close()


def db_clear_cart(sid: str):
    conn = get_conn()
    conn.execute("DELETE FROM cart_items WHERE session_id=?", (sid,))
    conn.commit()
    conn.close()


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
    conn.close()


def cart_count(sid: str) -> int:
    cart = db_get_cart(sid)
    return sum(int(i.get("quantity", 0)) for i in cart)


def cart_total(sid: str) -> float:
    cart = db_get_cart(sid)
    return round(sum(float(i.get("price", 0)) * int(i.get("quantity", 0)) for i in cart), 2)


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
    conn.close()
    return order_ids


# ── Products (SQL keyword search — no vector store) ────────────────────────

def get_all_products() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM products ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_products(query: str, limit: int = 8) -> list[dict]:
    """Pure SQL keyword search with scoring. No embeddings needed."""
    tokens = [t.strip().lower() for t in query.split() if len(t.strip()) > 1]
    if not tokens:
        return get_all_products()[:limit]

    conn = get_conn()
    rows = conn.execute("SELECT * FROM products WHERE quantity > 0").fetchall()
    conn.close()

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
    conn.close()
    return dict(row) if row else None


def get_product_by_id(pid: int) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    conn.close()
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
    conn.close()
    return pid


def update_product(pid: int, **kwargs):
    conn = get_conn()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [pid]
    conn.execute(f"UPDATE products SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE id=?", vals)
    conn.commit()
    conn.close()


def delete_product_row(pid: int) -> bool:
    conn = get_conn()
    cur = conn.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


# ── Analytics ───────────────────────────────────────────────────────────────

def get_summary_stats() -> dict:
    conn = get_conn()
    total_products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    total_revenue = conn.execute("SELECT COALESCE(SUM(price*quantity),0) FROM orders").fetchone()[0]
    total_customers = conn.execute("SELECT COUNT(DISTINCT session_id) FROM orders").fetchone()[0]
    conn.close()
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
    conn.close()
    return [dict(r) for r in rows]


def get_top_products(limit: int = 5) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT product_name, SUM(quantity) as total_sold, SUM(price*quantity) as revenue
           FROM orders GROUP BY product_name ORDER BY total_sold DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_revenue_by_category() -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT COALESCE(category,'other') as category, SUM(price*quantity) as revenue
           FROM orders GROUP BY category ORDER BY revenue DESC""",
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stock_levels() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT id,name,category,quantity,price FROM products ORDER BY quantity ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_orders(limit: int = 10) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Wishlist ────────────────────────────────────────────────────────────────

def add_to_wishlist(sid: str, product_id: int):
    ensure_session(sid)
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO wishlists (session_id,product_id) VALUES (?,?)",
        (sid, product_id),
    )
    conn.commit()
    conn.close()


def get_wishlist(sid: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT w.product_id, p.name, p.price, p.image_path
           FROM wishlists w JOIN products p ON p.id=w.product_id
           WHERE w.session_id=?""",
        (sid,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Try-on image helpers ────────────────────────────────────────────────────

def save_user_image(file_bytes: bytes, session_id: str, ext: str = ".jpg") -> str:
    out = Path(config.USER_IMAGES_DIR) / f"{session_id}{ext}"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(file_bytes)
    return str(out)


def save_product_image(file_bytes: bytes, product_name: str, ext: str = ".jpg") -> str:
    safe_name = product_name.lower().replace(" ", "_").replace("/", "_")
    out = Path(config.DB_IMAGES_DIR) / f"{safe_name}{ext}"
    counter = 1
    while out.exists():
        out = Path(config.DB_IMAGES_DIR) / f"{safe_name}_{counter}{ext}"
        counter += 1
    out.write_bytes(file_bytes)
    return str(out)
