"""Executor — calls tools directly as Python functions. No LLM involved."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging

from api.registry import get_registry
from api.schemas import ToolCall, ToolResult
from api.thread_pool import run_in_thread

logger = logging.getLogger(__name__)

# Fields the executor auto-injects into tool args
_AUTO_INJECT = {"session_id", "user_image_path"}
_SIGNATURE_CACHE: dict[str, inspect.Signature] = {}


def _signature_for(tool_name: str, tool_fn) -> inspect.Signature:
    cached = _SIGNATURE_CACHE.get(tool_name)
    if cached is not None:
        return cached
    # LangChain StructuredTool: sync tools use .func, async tools use .coroutine
    underlying = (
        getattr(tool_fn, "coroutine", None) or getattr(tool_fn, "func", None) or tool_fn
    )
    signature = inspect.signature(underlying)
    _SIGNATURE_CACHE[tool_name] = signature
    return signature


def _decode_tool_output(raw) -> dict:
    if isinstance(raw, str):
        return json.loads(raw)
    if isinstance(raw, dict):
        return raw
    return {"result": str(raw)}


def _guard_product_ids_call(registry, tc: ToolCall) -> ToolCall:
    if tc.tool != "get_products_by_ids":
        return tc

    args = dict(tc.args or {})
    raw_ids = args.get("product_ids")
    if not isinstance(raw_ids, list):
        raw_ids = []

    parsed_ids: list[int] = []
    for pid in raw_ids:
        try:
            parsed_ids.append(int(pid))
        except (TypeError, ValueError):
            continue

    valid_ids = registry.get_valid_product_ids()
    valid_set = set(valid_ids)
    kept = [pid for pid in parsed_ids if pid in valid_set]

    if kept:
        args["product_ids"] = list(dict.fromkeys(kept))
        if len(kept) != len(parsed_ids):
            logger.warning(
                "guardrail sanitized product_ids requested=%s kept=%s",
                parsed_ids,
                args["product_ids"],
            )
        return ToolCall(tool=tc.tool, args=args)

    fallback = registry.get_valid_product_ids(limit=max(len(parsed_ids), 3))
    args["product_ids"] = fallback
    logger.warning(
        "guardrail fallback product_ids requested=%s fallback=%s",
        parsed_ids,
        fallback,
    )
    return ToolCall(tool=tc.tool, args=args)


async def _execute_one_tool(
    registry, tc: ToolCall, session_id: str, user_image_path: str | None
) -> ToolResult:
    tool_name = tc.tool
    args = dict(tc.args)

    try:
        tool_fn = registry.get_tool(tool_name)
        sig = _signature_for(tool_name, tool_fn)

        if "session_id" in sig.parameters and "session_id" not in args:
            args["session_id"] = session_id
        if "user_image_path" in sig.parameters and "user_image_path" not in args:
            if user_image_path:
                args["user_image_path"] = user_image_path

        logger.info("execute tool=%s args=%s", tool_name, args)
        is_async = getattr(tool_fn, "coroutine", None) is not None
        if is_async:
            raw = await tool_fn.ainvoke(args)
        else:
            raw = await run_in_thread(tool_fn.invoke, args)
        data = _decode_tool_output(raw)

        logger.info(
            "execute done tool=%s success=True keys=%s", tool_name, sorted(data.keys())
        )
        return ToolResult(tool=tool_name, success=True, data=data)

    except Exception as e:
        logger.exception("execute failed tool=%s", tool_name)
        return ToolResult(tool=tool_name, success=False, data={}, error=str(e))


async def _execute_parallel_batch(
    registry,
    batch: list[ToolCall],
    session_id: str,
    user_image_path: str | None,
) -> list[ToolResult]:
    if not batch:
        return []
    if len(batch) == 1:
        return [
            await _execute_one_tool(registry, batch[0], session_id, user_image_path)
        ]

    logger.info("execute parallel batch tools=%s", [tc.tool for tc in batch])
    results = await asyncio.gather(
        *(_execute_one_tool(registry, tc, session_id, user_image_path) for tc in batch)
    )
    return list(results)


async def execute_tools(
    tool_calls: list[ToolCall],
    session_id: str,
    user_image_path: str | None = None,
) -> list[ToolResult]:
    """Execute tool calls directly. No LLM calls — pure function dispatch.

    Args:
        tool_calls: List of ToolCall from the planner.
        session_id: Current session ID (auto-injected into tools that need it).
        user_image_path: Path to uploaded user image (for try-on).

    Returns:
        List of ToolResult with structured data from each tool.
    """
    registry = get_registry()
    results: list[ToolResult] = []
    parallel_batch: list[ToolCall] = []

    for tc in tool_calls:
        tc = _guard_product_ids_call(registry, tc)
        if registry.is_parallel_safe(tc.tool):
            parallel_batch.append(tc)
            continue

        results.extend(
            await _execute_parallel_batch(
                registry, parallel_batch, session_id, user_image_path
            )
        )
        parallel_batch = []
        results.append(
            await _execute_one_tool(registry, tc, session_id, user_image_path)
        )

    results.extend(
        await _execute_parallel_batch(
            registry, parallel_batch, session_id, user_image_path
        )
    )
    return results
