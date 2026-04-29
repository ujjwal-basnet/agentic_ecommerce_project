"""Shared ThreadPoolExecutor utilities for blocking work."""

from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Callable

_executor: ThreadPoolExecutor | None = None


def _default_max_workers() -> int:
    cpu = os.cpu_count() or 1
    return min(32, cpu + 4)


def init_thread_pool(max_workers: int | None = None) -> ThreadPoolExecutor:
    """Initialize and return the shared thread pool."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=max_workers or _default_max_workers(),
            thread_name_prefix="smartshop-worker",
        )
    return _executor


def get_thread_pool() -> ThreadPoolExecutor:
    """Get the shared thread pool, creating it on first use."""
    return _executor or init_thread_pool()


async def run_in_thread(func: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
    """Run blocking callable on the shared ThreadPoolExecutor."""
    loop = asyncio.get_running_loop()
    call = partial(func, *args, **kwargs) if kwargs else partial(func, *args)
    return await loop.run_in_executor(get_thread_pool(), call)


def shutdown_thread_pool(wait: bool = True, cancel_futures: bool = False) -> None:
    """Shutdown the shared thread pool cleanly."""
    global _executor
    if _executor is None:
        return
    _executor.shutdown(wait=wait, cancel_futures=cancel_futures)
    _executor = None
