"""Postgres connection pool and sqlite-style query wrapper."""

from __future__ import annotations

import threading

import psycopg2
import psycopg2.pool

from api import config
from api.db.row import Row

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


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


def _init_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """Lazy-init a process-wide connection pool."""
    global _pool
    if _pool is None:
        if not config.DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is required. Set it to the Supabase Postgres connection string "
                "in backend .env or Render environment variables."
            )
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=15,
            dsn=config.DATABASE_URL,
            sslmode=config.DB_SSLMODE,
            connect_timeout=10,
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=5,
        )
    return _pool


def _connection_is_usable(raw) -> bool:
    """Return False for stale pooled connections killed by Supabase/network idle timeouts."""
    if raw.closed:
        return False
    cursor = raw.cursor()
    try:
        cursor.execute("SELECT 1")
        raw.rollback()
        return True
    except (psycopg2.InterfaceError, psycopg2.OperationalError):
        try:
            raw.close()
        except Exception:
            pass
        return False
    finally:
        try:
            cursor.close()
        except Exception:
            pass


def get_conn() -> PostgresConnection:
    """Return a live pooled connection keyed by thread id.

    Supabase pooler connections can go stale after idle periods. The old code
    reused thread-keyed connections without a health check, so the first chat
    after a pause could fail with "could not send data to server".
    """
    key = threading.current_thread().ident
    pool = _init_pool()
    raw = pool.getconn(key=key)
    if not _connection_is_usable(raw):
        pool.putconn(raw, key=key, close=True)
        raw = pool.getconn(key=key)
    return PostgresConnection(raw)


def close_pool():
    """Shutdown the connection pool (call during app shutdown)."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None
