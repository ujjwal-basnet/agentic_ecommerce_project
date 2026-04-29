"""Order helpers."""

from __future__ import annotations

from api.db.cart import db_get_cart
from api.db.pool import get_conn


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
            (
                sid,
                item.get("product_id"),
                item["product_name"],
                item.get("category", ""),
                float(item["price"]),
                int(item["quantity"]),
            ),
        )
        order_ids.append(cur.fetchone()["id"])
    conn.execute("DELETE FROM cart_items WHERE session_id=?", (sid,))
    conn.commit()
    return order_ids


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
