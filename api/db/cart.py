"""Cart CRUD helpers."""

from __future__ import annotations

from api.db.pool import get_conn
from api.db.users import ensure_session


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
        conn.execute(
            "UPDATE cart_items SET quantity=quantity+? WHERE id=?",
            (quantity, row["id"]),
        )
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
        conn.execute(
            "DELETE FROM cart_items WHERE session_id=? AND product_name=?",
            (sid, product_name),
        )
    else:
        conn.execute(
            "UPDATE cart_items SET quantity=? WHERE session_id=? AND product_name=?",
            (quantity, sid, product_name),
        )
    conn.commit()


def cart_totals(cart: list[dict]) -> tuple[int, float]:
    """Compute (item_count, total_price) from a cart items list."""
    count = sum(int(i.get("quantity", 0)) for i in cart)
    total = round(
        sum(float(i.get("price", 0)) * int(i.get("quantity", 0)) for i in cart), 2
    )
    return count, total


def cart_count(sid: str) -> int:
    conn = get_conn()
    row = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) FROM cart_items WHERE session_id=?", (sid,)
    ).fetchone()
    return int(row[0]) if row else 0


def cart_total(sid: str) -> float:
    cart = db_get_cart(sid)
    _, total = cart_totals(cart)
    return total
