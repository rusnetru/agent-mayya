"""Goal Management System (Phase 3.1).

Goal Stack:
  [Long-term goal]
    [Mid-term objective]
      [Current task]
        [Immediate action]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Horizon = Literal["long_term", "mid_term", "task", "action"]

_NEXT_HORIZON: dict[Horizon, Horizon] = {
    "long_term": "mid_term",
    "mid_term": "task",
    "task": "action",
}


@dataclass
class Goal:
    description: str
    horizon: Horizon
    parent: "Goal | None" = None
    children: list["Goal"] = field(default_factory=list)
    active: bool = True


class GoalStack:
    """Hierarchy of goals with different time horizons."""

    def __init__(self) -> None:
        self.roots: list[Goal] = []

    def push(self, description: str, horizon: Horizon = "long_term", parent: Goal | None = None) -> Goal:
        goal = Goal(description=description, horizon=horizon, parent=parent)
        if parent is None:
            self.roots.append(goal)
        else:
            parent.children.append(goal)
        return goal

    def decompose(self, goal: Goal, subgoal_descriptions: list[str]) -> list[Goal]:
        """Break a goal down into subgoals one horizon level more concrete."""
        next_horizon = _NEXT_HORIZON.get(goal.horizon)
        if next_horizon is None:
            raise ValueError(f"goal at horizon '{goal.horizon}' cannot be decomposed further")
        return [self.push(desc, horizon=next_horizon, parent=goal) for desc in subgoal_descriptions]

    def revise(self, goal: Goal, new_description: str | None = None, active: bool | None = None) -> None:
        """Revisit a goal when context changes — update description and/or deactivate it."""
        if new_description is not None:
            goal.description = new_description
        if active is not None:
            goal.active = active

    def active_leaves(self) -> list[Goal]:
        """Innermost active goals (no active children) — what should be worked on now."""
        leaves: list[Goal] = []

        def walk(goal: Goal) -> None:
            if not goal.active:
                return
            active_children = [c for c in goal.children if c.active]
            if not active_children:
                leaves.append(goal)
            else:
                for child in active_children:
                    walk(child)

        for root in self.roots:
            walk(root)
        return leaves
