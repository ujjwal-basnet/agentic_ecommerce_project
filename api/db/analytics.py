"""Analytics and tracking query helpers."""

from __future__ import annotations

from api.db.pool import get_conn
from api.db.users import ensure_session


def get_summary_stats() -> dict:
    conn = get_conn()
    total_products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    total_revenue = conn.execute(
        "SELECT COALESCE(SUM(price*quantity),0) FROM orders"
    ).fetchone()[0]
    total_customers = conn.execute(
        "SELECT COUNT(DISTINCT session_id) FROM orders"
    ).fetchone()[0]
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
    rows = conn.execute(
        "SELECT id,name,category,quantity,price FROM products ORDER BY quantity ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_recent_orders(limit: int = 10) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def log_product_view(
    session_id: str, product_id: int, search_query: str | None = None
) -> None:
    ensure_session(session_id)
    conn = get_conn()
    conn.execute(
        "INSERT INTO product_views (session_id, product_id, search_query) VALUES (?, ?, ?)",
        (session_id, product_id, search_query),
    )
    conn.commit()


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
        out.append(
            {
                "date": d,
                "revenue": float(o.get("revenue") or 0),
                "units": int(o.get("units") or 0),
                "cart_adds": int(cart_map.get(d, 0)),
                "views": int(view_map.get(d, 0)),
            }
        )
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
