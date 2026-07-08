"""Knowledge-base query helpers."""

from __future__ import annotations

import logging
import re

from api.db.pool import PostgresConnection, get_conn

logger = logging.getLogger(__name__)

_KB_SEED = [
    (
        "Return & Refund Policy",
        "returns",
        "We accept returns within 7 days of delivery for clothing items. Items must be unused, unworn, in original packaging, "
        "and with tags attached. Refunds are processed within 24-48 hours directly to your eSewa, Khalti, or bank account "
        "after our warehouse receives and inspects the item. Electronics and items bought during flash sales are final sale "
        "and cannot be returned. Returns can be initiated from your account dashboard or by contacting customer support.",
    ),
    (
        "Shipping & Delivery Policy",
        "shipping",
        "We deliver to all major cities across Nepal. Inside Kathmandu Valley, delivery takes 24-48 hours and is free "
        "for orders above Rs. 1500 (flat Rs. 100 for orders under Rs. 1500). Delivery outside Kathmandu Valley (e.g. Pokhara, "
        "Butwal, Biratnagar, Chitwan) takes 3-5 business days with a flat rate of Rs. 150. COD (Cash on Delivery) is available "
        "for orders up to Rs. 15,000 nationwide. Orders above Rs. 15,000 require a 10% advance payment via eSewa or Khalti.",
    ),
    (
        "Size & Fitting Guide",
        "sizing",
        "Our clothing follows standard Nepalese/South Asian sizes: Shirts and T-Shirts range from S (36) to XXL (44). "
        "Womens Kurtis are available in S (36), M (38), L (40), and XL (42). Straight-fit Jeans are sized from 28 to 36 inches. "
        "Detailed measurements are displayed on each product card. If you are in between sizes, we recommend ordering one size "
        "up for a comfortable fit.",
    ),
    (
        "Payment & Checkout Methods",
        "payment",
        "SmartShop supports multiple payment gateways for your convenience: eSewa, Khalti, direct Bank Transfer (IPS/ConnectIPS), "
        "and Cash on Delivery (COD). Cash on Delivery is available for all orders under Rs. 15,000. Online payments are "
        "processed through secure SSL encryption, and you will be redirected to the respective payment app during checkout.",
    ),
    (
        "Virtual Try-On Guide",
        "tryon",
        "Our innovative Virtual Try-On feature allows you to see how clothing looks on you before buying! Click on any wearable "
        "garment (shirts, kurtis, jeans) and choose 'Virtual Try-On'. Upload a clear, front-facing, full-body photo of yourself "
        "in standard lighting. Our AI model overlays the clothing in real-time. For privacy, your uploaded photos are "
        "processed in volatile memory and permanently deleted immediately after generation.",
    ),
    (
        "SmartShop Points & Rewards",
        "rewards",
        "Earn while you shop with our SmartShop Loyalty Program! Get 5% cashback in the form of SmartPoints for every Rs. 100 spent. "
        "1 SmartPoint is equivalent to Rs. 1 and can be redeemed during checkout for instant discounts. Points are credited "
        "automatically to your account once your order is successfully delivered. Points do not expire.",
    ),
    (
        "Store Contact & Customer Support",
        "contact",
        "Our online store is open 24/7 for browsing and ordering. Live customer support is available from 10 AM to 6 PM NPT, "
        "Sunday to Friday. You can email us at support@smartshop.com.np, call +977-1-4567890, or message us directly on our "
        "Facebook and Instagram pages. Response times are typically under 2 hours during support hours.",
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
