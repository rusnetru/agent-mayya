"""Observability — memory/goal state snapshot for a monitoring dashboard (Phase 5.1).

`snapshot()` produces a plain-dict summary suitable for rendering in a CLI
table, a web dashboard, or shipping to an external metrics sink — it touches
only the public APIs of Memory (Phase 1) and GoalStack (Phase 3).
"""

from __future__ import annotations

from typing import Any

from src.goals.goal_stack import GoalStack
from src.memory.api import Memory


def snapshot(memory: Memory, goals: GoalStack | None = None) -> dict[str, Any]:
    state: dict[str, Any] = {
        "working_memory": memory.working.as_list(),
        "episodic_count": memory.episodic.count(),
        "skills": {
            name: {"uses": s.uses, "successes": s.successes, "success_rate": s.success_rate}
            for name, s in memory.skills.all().items()
        },
    }
    if goals is not None:
        state["active_goals"] = [
            {"description": g.description, "horizon": g.horizon} for g in goals.active_leaves()
        ]
    return state
