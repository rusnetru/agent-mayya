"""Episodic Memory Engine (Phase 1.1) — SQLite persistence + hybrid vector retrieval.

Captures events with full metadata (timestamp, who, where, why) and supports
single-shot learning (no gradient updates: an episode is usable for retrieval
the instant it's stored) and hybrid vector+keyword retrieval.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.memory.vector_index import VectorIndex


@dataclass
class Episode:
    content: str
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    who: str | None = None
    where: str | None = None
    why: str | None = None
    id: int | None = None


class EpisodicMemory:
    """Persists episodes to a SQLite file. Pass db_path=":memory:" for ephemeral use (tests)."""

    def __init__(self, db_path: str | Path = "memory.db", vector_index=None) -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                context TEXT NOT NULL,
                timestamp REAL NOT NULL,
                who TEXT,
                where_ TEXT,
                why TEXT
            )
            """
        )
        self._conn.commit()
        self._vector_index = vector_index if vector_index is not None else VectorIndex()
        for episode in self.all():
            self._vector_index.add(episode.id, episode.content)

    def store(
        self,
        content: str,
        context: dict[str, Any] | None = None,
        who: str | None = None,
        where: str | None = None,
        why: str | None = None,
    ) -> Episode:
        episode = Episode(content=content, context=context or {}, who=who, where=where, why=why)
        cursor = self._conn.execute(
            "INSERT INTO episodes (content, context, timestamp, who, where_, why) VALUES (?, ?, ?, ?, ?, ?)",
            (episode.content, json.dumps(episode.context), episode.timestamp, who, where, why),
        )
        self._conn.commit()
        episode.id = cursor.lastrowid
        self._vector_index.add(episode.id, episode.content)
        return episode

    def retrieve(self, query: str, top_k: int = 5) -> list[Episode]:
        """Hybrid retrieval: union of exact substring matches and vector-similarity matches."""
        by_id = {e.id: e for e in self.all()}
        keyword_matches = [e for e in by_id.values() if query.lower() in e.content.lower()]
        vector_hits = self._vector_index.search(query, top_k=top_k)

        ranked: list[Episode] = []
        seen: set[int] = set()
        for item_id, _score in vector_hits:
            if item_id in by_id and item_id not in seen:
                ranked.append(by_id[item_id])
                seen.add(item_id)
        for episode in reversed(keyword_matches):
            if episode.id not in seen:
                ranked.append(episode)
                seen.add(episode.id)
        return ranked[:top_k]

    def all(self) -> list[Episode]:
        rows = self._conn.execute(
            "SELECT id, content, context, timestamp, who, where_, why FROM episodes ORDER BY id"
        ).fetchall()
        return [
            Episode(
                id=eid,
                content=c,
                context=json.loads(ctx),
                timestamp=ts,
                who=who,
                where=where,
                why=why,
            )
            for eid, c, ctx, ts, who, where, why in rows
        ]

    def count(self) -> int:
        (n,) = self._conn.execute("SELECT COUNT(*) FROM episodes").fetchone()
        return n

    def forget_before(self, cutoff_timestamp: float) -> int:
        """Evict episodes older than cutoff. Returns count evicted."""
        rows = self._conn.execute(
            "SELECT id FROM episodes WHERE timestamp < ?", (cutoff_timestamp,)
        ).fetchall()
        ids = [r[0] for r in rows]
        if not ids:
            return 0
        self._conn.execute(
            f"DELETE FROM episodes WHERE id IN ({','.join('?' * len(ids))})", ids
        )
        self._conn.commit()
        for item_id in ids:
            self._vector_index.remove(item_id)
        return len(ids)

    def close(self) -> None:
        self._conn.close()
