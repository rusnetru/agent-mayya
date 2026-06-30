"""Planning Engine (Phase 3.2).

Базовый:  ReAct loop с self-critique (Reflexion-style).
Расширенный: упрощённый MCTS для выбора действий (LATS-inspired).
Мета: выбор стратегии планирования по накопленной статистике успеха
(TodoEvolve-inspired — агент не пишет код заново, а выбирает между
зарегистрированными стратегиями на основе истории).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Callable

ActFn = Callable[[str], str]
CritiqueFn = Callable[[str, str], str | None]  # (task, result) -> feedback or None if good


@dataclass
class PlanResult:
    task: str
    final_result: str
    attempts: int
    critiques: list[str] = field(default_factory=list)


def react_with_self_critique(
    task: str,
    act: ActFn,
    critique: CritiqueFn,
    max_iterations: int = 3,
) -> PlanResult:
    """Reflexion-style loop: act, critique the result, retry with feedback folded
    into the next attempt's task framing, until critique passes or budget runs out.
    """
    critiques: list[str] = []
    current_task = task
    result = ""
    for attempt in range(1, max_iterations + 1):
        result = act(current_task)
        feedback = critique(task, result)
        if feedback is None:
            return PlanResult(task=task, final_result=result, attempts=attempt, critiques=critiques)
        critiques.append(feedback)
        current_task = f"{task} (retry, feedback: {feedback})"
    return PlanResult(task=task, final_result=result, attempts=max_iterations, critiques=critiques)


@dataclass
class MCTSNode:
    action: str | None
    parent: "MCTSNode | None" = None
    children: list["MCTSNode"] = field(default_factory=list)
    visits: int = 0
    value: float = 0.0

    def ucb1(self, exploration: float = 1.41) -> float:
        if self.visits == 0:
            return float("inf")
        parent_visits = self.parent.visits if self.parent else 1
        return (self.value / self.visits) + exploration * math.sqrt(
            math.log(max(parent_visits, 1)) / self.visits
        )


def mcts_select_action(
    actions: list[str],
    simulate: Callable[[str], float],
    iterations: int = 50,
    seed: int | None = None,
) -> str:
    """Toy MCTS over a flat action set: each action is a root child, simulated
    repeatedly via `simulate` (reward in [0, 1]), best mean-reward action wins.
    """
    if not actions:
        raise ValueError("actions must be non-empty")
    rng = random.Random(seed)
    root = MCTSNode(action=None)
    root.children = [MCTSNode(action=a, parent=root) for a in actions]

    for _ in range(iterations):
        node = rng.choice(root.children)
        reward = simulate(node.action)  # type: ignore[arg-type]
        node.visits += 1
        node.value += reward
        root.visits += 1

    best = max(root.children, key=lambda n: (n.value / n.visits) if n.visits else -1.0)
    return best.action  # type: ignore[return-value]


class StrategyRegistry:
    """Meta layer: tracks which planning strategy works best for which task class,
    and adapts the choice over time instead of hardcoding one strategy.
    """

    def __init__(self) -> None:
        self._stats: dict[tuple[str, str], list[float]] = {}

    def record(self, task_class: str, strategy: str, success: bool) -> None:
        key = (task_class, strategy)
        self._stats.setdefault(key, []).append(1.0 if success else 0.0)

    def best_strategy(self, task_class: str, available: list[str]) -> str:
        """Pick the strategy with the highest observed success rate for this task
        class; falls back to the first available strategy if there's no history.
        """
        scored = []
        for strategy in available:
            history = self._stats.get((task_class, strategy), [])
            rate = sum(history) / len(history) if history else 0.5  # unexplored = neutral prior
            scored.append((rate, strategy))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return scored[0][1]
