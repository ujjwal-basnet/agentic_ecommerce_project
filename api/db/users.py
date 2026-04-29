"""Users, sessions, and chat history."""

from __future__ import annotations

from api.db.pool import get_conn


def ensure_session(sid: str):
    if not sid or not sid.strip():
        raise ValueError("session_id is required")
    conn = get_conn()
    conn.execute(
        "INSERT INTO sessions (id) VALUES (?) ON CONFLICT (id) DO UPDATE SET last_active=NOW()",
        (sid,),
    )
    conn.commit()


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
    conn.execute(
        "UPDATE orders SET user_id = ? WHERE session_id = ? AND user_id IS NULL",
        (user_id, session_id),
    )
    conn.execute(
        "UPDATE cart_items SET user_id = ? WHERE session_id = ? AND user_id IS NULL",
        (user_id, session_id),
    )
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


def delete_account_by_session(session_id: str) -> bool:
    """Delete the customer account bound to a session and purge its user data."""
    conn = get_conn()
    row = conn.execute(
        "SELECT user_id FROM sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    user_id = row["user_id"] if row and row["user_id"] is not None else None

    if user_id is None:
        conn.execute("DELETE FROM product_views WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM orders WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM cart_items WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM wishlists WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        return False

    conn.execute("DELETE FROM product_views WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM orders WHERE user_id = ? OR session_id = ?", (user_id, session_id))
    conn.execute("DELETE FROM cart_items WHERE user_id = ? OR session_id = ?", (user_id, session_id))
    conn.execute("DELETE FROM wishlists WHERE user_id = ? OR session_id = ?", (user_id, session_id))
    conn.execute("DELETE FROM sessions WHERE user_id = ? OR id = ?", (user_id, session_id))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    return True
