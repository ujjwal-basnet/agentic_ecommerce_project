"""In-process product catalog cache.

We do NOT do semantic query caching (dropped Redis). Pinecone is already fast
for vector search and the planner only runs one LLM call per request, so the
extra cache layer is not worth the complexity for now.

ProductCache is a simple in-process TTL cache around the Postgres product list
so the registry/planner doesn't re-query on every turn.
"""

from __future__ import annotations

import logging
import time
from threading import Lock

logger = logging.getLogger(__name__)


class ProductCache:
    """Thread-safe in-process TTL cache for the product catalog."""

    def __init__(self, ttl: int = 300) -> None:
        self._ttl = ttl
        self._value: list[dict] | None = None
        self._expires_at: float = 0.0
        self._lock = Lock()

    def get_all(self) -> list[dict] | None:
        with self._lock:
            if self._value is None or time.time() > self._expires_at:
                return None
            return self._value

    def set_all(self, products: list[dict]) -> None:
        with self._lock:
            self._value = products
            self._expires_at = time.time() + self._ttl

    def invalidate(self) -> None:
        with self._lock:
            self._value = None
            self._expires_at = 0.0


_product_cache: ProductCache | None = None


def get_product_cache() -> ProductCache:
    global _product_cache
    if _product_cache is None:
        _product_cache = ProductCache()
    return _product_cache
