"""Memory API v1 — unified facade over working, episodic, semantic, and skill stores.

Spec (docs/02_development_plan.md, section 1.4):
    memory.store(event, type="episodic", context={...})
    memory.retrieve(query, top_k=5, types=["episodic", "semantic"])
    memory.consolidate()        # episodic -> semantic
    memory.skill_extract(episode_id)  # auto-extract a skill
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from src.memory.episodic import Episode, EpisodicMemory
from src.memory.semantic import SemanticGraph
from src.memory.skills import Skill, SkillStore
from src.memory.working import WorkingMemory

MemoryType = Literal["episodic", "semantic"]


class Memory:
    def __init__(
        self,
        db_path: str | Path = "memory.db",
        working_capacity: int = 20,
        consolidate_every: int = 5,
        safety_guard=None,
        vector_index=None,
    ) -> None:
        self.working = WorkingMemory(capacity=working_capacity)
        self.episodic = EpisodicMemory(db_path=db_path, vector_index=vector_index)
        self.semantic = SemanticGraph()
        self.skills = SkillStore()
        self.consolidate_every = consolidate_every
        self._guard = safety_guard  # MemorySafetyGuard | None

    def store(
        self,
        event: str,
        type: MemoryType = "episodic",
        context: dict[str, Any] | None = None,
        who: str | None = None,
        where: str | None = None,
        why: str | None = None,
    ) -> Episode:
        self.working.add(event)
        if type == "semantic":
            self._add_semantic_fact(event, context or {})
        episode = self.episodic.store(event, context, who=who, where=where, why=why)
        if self.consolidate_every and self.episodic.count() % self.consolidate_every == 0:
            self.consolidate()
        return episode

    def _add_semantic_fact(self, fact: str, metadata: dict[str, Any]) -> bool:
        if self._guard is not None:
            return self._guard.propose_fact(fact, metadata)
        self.semantic.add_fact(fact, metadata)
        return True

    def forget(self, cutoff_timestamp: float) -> int:
        """Evict episodic memories older than cutoff_timestamp. Returns count evicted."""
        return self.episodic.forget_before(cutoff_timestamp)

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        types: list[MemoryType] | None = None,
    ) -> dict[str, list[Any]]:
        types = types or ["episodic", "semantic"]
        result: dict[str, list[Any]] = {}
        if "episodic" in types:
            result["episodic"] = self.episodic.retrieve(query, top_k=top_k)
        if "semantic" in types:
            result["semantic"] = self.semantic.query(query, top_k=top_k)
        return result

    def consolidate(self) -> int:
        """Promote recurring episodic patterns into semantic facts. Returns count promoted."""
        promoted = 0
        seen: dict[str, int] = {}
        for episode in self.episodic.all():
            seen[episode.content] = seen.get(episode.content, 0) + 1
        for content, count in seen.items():
            if count >= 2 and not self.semantic.has_fact(content):
                meta = {"source": "consolidation", "frequency": count}
                if self._add_semantic_fact(content, meta):
                    promoted += 1
        return promoted

    def skill_extract(self, episode_index: int) -> Skill | None:
        episodes = self.episodic.all()
        if episode_index < 0 or episode_index >= len(episodes):
            return None
        episode = episodes[episode_index]
        plan = episode.context.get("plan")
        if not plan:
            return None
        return self.skills.extract(name=episode.content, procedure=plan)

    def close(self) -> None:
        self.episodic.close()
