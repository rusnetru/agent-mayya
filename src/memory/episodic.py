"""Episodic memory store — Phase 0 stub (in-memory, no persistence yet)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Episode:
    content: str
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class EpisodicMemory:
    def __init__(self) -> None:
        self._episodes: list[Episode] = []

    def store(self, content: str, context: dict[str, Any] | None = None) -> Episode:
        episode = Episode(content=content, context=context or {})
        self._episodes.append(episode)
        return episode

    def retrieve(self, query: str, top_k: int = 5) -> list[Episode]:
        matches = [e for e in self._episodes if query.lower() in e.content.lower()]
        return matches[-top_k:]
