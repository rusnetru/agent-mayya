"""Observability — full action tracing (Phase 5.1).

A single in-process Tracer records every notable action across the agent
(orchestrator dispatch, memory writes, goal revisions, ...) as a structured
event, exportable as JSON for an external dashboard/log pipeline.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TraceEvent:
    component: str
    action: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class Tracer:
    def __init__(self) -> None:
        self._events: list[TraceEvent] = []

    def record(self, component: str, action: str, data: dict[str, Any] | None = None) -> TraceEvent:
        event = TraceEvent(component=component, action=action, data=data or {})
        self._events.append(event)
        return event

    def events(self) -> list[TraceEvent]:
        return list(self._events)

    def by_component(self, component: str) -> list[TraceEvent]:
        return [e for e in self._events if e.component == component]

    def export(self) -> list[dict[str, Any]]:
        return [asdict(e) for e in self._events]

    def clear(self) -> None:
        self._events.clear()
