"""Execution trace schema for glass-box debugging."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any


@dataclass
class ExecutionTrace:
    session_id: str
    started_at: float = field(default_factory=perf_counter)
    timings_ms: dict[str, int] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    def add(self, event: str, **data: Any) -> None:
        self.events.append({"event": event, **data})

    def mark(self, name: str, started_at: float) -> None:
        self.timings_ms[name] = int((perf_counter() - started_at) * 1000)
