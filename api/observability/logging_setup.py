"""Structured JSON logging — stdlib only, no extra deps.

Each record emits one JSON line with timestamp, level, logger, message, and the
current request_id (if any). Keeps NPT timezone for human readability of `ts`.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone, timedelta

from .request_context import current_request_id

_NPT = timezone(timedelta(hours=5, minutes=45))

_RESERVED = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        dt = datetime.fromtimestamp(record.created, tz=_NPT)
        payload: dict = {
            "ts": dt.isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        rid = current_request_id()
        if rid:
            payload["request_id"] = rid
        # Forward any extras passed via logger.info("...", extra={...}).
        for k, v in record.__dict__.items():
            if k in _RESERVED or k.startswith("_"):
                continue
            try:
                json.dumps(v, default=str)
                payload[k] = v
            except (TypeError, ValueError):
                payload[k] = repr(v)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class _NptText(logging.Formatter):
    """Human-friendly NPT formatter for local dev (LOG_FORMAT=text)."""

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=_NPT)
        return dt.strftime("%b %-d, %-I:%M:%S%p").lower()


def setup_logging() -> None:
    """Initialize root logger. LOG_FORMAT=text|json (default json)."""
    fmt = os.getenv("LOG_FORMAT", "json").lower()
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    if fmt == "text":
        formatter = _NptText("%(asctime)s  %(levelname)-8s  %(name)s  %(message)s")
    else:
        formatter = JsonFormatter()

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)
