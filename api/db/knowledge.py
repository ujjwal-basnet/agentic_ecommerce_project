"""Knowledge-base query helpers."""

from __future__ import annotations

import logging
import re

from api.db.pool import PostgresConnection, get_conn

logger = logging.getLogger(__name__)

_KB_SEED = [
    (
        "Return Policy",
        "returns",
        "We accept returns within 7 days of delivery. Items must be unused, in original packaging, "
        "with tags attached. Refunds are processed within 3-5 business days after we receive the item. "
        "Electronics and sale items are final sale and cannot be returned. To initiate a return, "
        "go to your order history and select 'Request Return' or contact support.",
    ),
    (
        "Shipping Information",
        "shipping",
        "We ship across Nepal. Standard delivery takes 3-5 business days and costs Rs. 100 for orders "
        "under Rs. 2000 (free above Rs. 2000). Express delivery (1-2 days) is Rs. 250. We ship via "
        "local courier partners. You will receive a tracking update when your order is dispatched. "
        "Cash on delivery is available for orders under Rs. 10,000.",
    ),
    (
        "Size Guide",
        "sizing",
        "Our clothing follows standard South Asian sizing. Shirts: S (36), M (38), L (40), XL (42), "
        "XXL (44). Kurtis: S (36), M (38), L (40), XL (42). Jeans: 28, 30, 32, 34, 36. "
        "If you are between sizes, we recommend going one size up. Measurements are in inches (chest). "
        "For exact fit, refer to the product description for specific measurements.",
    ),
    (
        "Payment Methods",
        "payment",
        "We accept eSewa, Khalti, bank transfer, and cash on delivery. Online payments are processed "
        "securely. Cash on delivery is available for orders under Rs. 10,000. For eSewa/Khalti, "
        "you will be redirected to the payment gateway during checkout.",
    ),
    (
        "Store Hours & Contact",
        "contact",
        "Our online store is available 24/7. Customer support is available 10 AM - 6 PM NPT, "
        "Sunday to Friday. Email: support@smartshop.com.np. Phone: +977-1-XXXXXXX. "
        "Response time is typically within 24 hours.",
    ),
    (
        "Warranty & Quality",
        "warranty",
        "Electronics carry a 1-year manufacturer warranty. Clothing and accessories are guaranteed "
        "against manufacturing defects for 30 days. Bags carry a 6-month warranty on zippers and "
        "stitching. Warranty does not cover normal wear and tear or misuse.",
    ),
    (
        "Account & Privacy",
        "privacy",
        "We collect your name and email for order processing. Your data is never sold to third parties. "
        "Chat history is stored to improve your shopping experience. You can delete your account and "
        "all associated data by contacting support.",
    ),
]


def _seed_knowledge_base(conn: PostgresConnection) -> None:
    """Seed knowledge base if empty."""
    count = conn.execute("SELECT COUNT(*) FROM knowledge_base").fetchone()[0]
    if count > 0:
        return
    for title, category, content in _KB_SEED:
        conn.execute(
            "INSERT INTO knowledge_base (title, category, content) VALUES (?, ?, ?)",
            (title, category, content),
        )
    conn.commit()
    logger.info("Seeded %d knowledge base entries", len(_KB_SEED))


def search_knowledge_base(query: str, limit: int = 3) -> list[dict]:
    """Full-text search over the knowledge base for FAQ/policy questions."""
    tokens = [
        re.sub(r"[^a-z0-9]", "", t.lower()) for t in query.split() if len(t.strip()) > 1
    ]
    tokens = [t for t in tokens if t]
    if not tokens:
        return []

    conn = get_conn()
    tsquery_str = " | ".join(tokens)
    doc_expr = "to_tsvector('simple', title || ' ' || category || ' ' || content)"
    rows = conn.execute(
        f"SELECT id, title, category, content, ts_rank({doc_expr}, to_tsquery('simple', ?)) AS rank "
        f"FROM knowledge_base WHERE {doc_expr} @@ to_tsquery('simple', ?) "
        f"ORDER BY rank DESC LIMIT ?",
        (tsquery_str, tsquery_str, limit),
    ).fetchall()

    if rows:
        return [dict(r) for r in rows]

    # Fallback: ILIKE
    pattern = "%" + "%".join(tokens) + "%"
    rows = conn.execute(
        "SELECT id, title, category, content FROM knowledge_base "
        "WHERE LOWER(title) LIKE ? OR LOWER(category) LIKE ? OR LOWER(content) LIKE ? LIMIT ?",
        (pattern, pattern, pattern, limit),
    ).fetchall()
    return [dict(r) for r in rows]
