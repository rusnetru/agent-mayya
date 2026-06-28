"""Phase 0 agent loop: perceive -> retrieve -> plan -> act -> observe -> store."""

from __future__ import annotations

from src.memory.episodic import EpisodicMemory


class Agent:
    def __init__(self) -> None:
        self.memory = EpisodicMemory()

    def step(self, perception: str) -> str:
        related = self.memory.retrieve(perception)
        plan = self._plan(perception, related)
        result = self._act(plan)
        self.memory.store(perception, context={"plan": plan, "result": result})
        return result

    def _plan(self, perception: str, related: list) -> str:
        return f"respond to: {perception}"

    def _act(self, plan: str) -> str:
        return f"[stub action] {plan}"
