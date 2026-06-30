"""Self-Correction Loops (Phase 3.4).

Inner loop:  act -> verify -> retry  (per action)
Outer loop:  episode -> reflect -> update strategy  (per task)
Meta loop:   project -> consolidate -> evolve capabilities  (long-term)

Each loop is a small generic driver over caller-supplied callables so it can
wrap the Phase 2 Orchestrator, the Phase 3 Planning Engine, or plain
functions without coupling to either.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, TypeVar

T = TypeVar("T")


@dataclass
class InnerLoopResult:
    result: T | None
    attempts: int
    succeeded: bool


def inner_loop(
    act: Callable[[int], T],
    verify: Callable[[T], bool],
    max_retries: int = 3,
) -> InnerLoopResult:
    """Per-action loop: act, verify, retry on failure up to max_retries."""
    result: T | None = None
    for attempt in range(1, max_retries + 1):
        result = act(attempt)
        if verify(result):
            return InnerLoopResult(result=result, attempts=attempt, succeeded=True)
    return InnerLoopResult(result=result, attempts=max_retries, succeeded=False)


@dataclass
class OuterLoopResult:
    episodes_run: int
    final_strategy: str


def outer_loop(
    run_episode: Callable[[str], bool],
    reflect: Callable[[bool], str | None],
    strategies: list[str],
    max_episodes: int = 5,
) -> OuterLoopResult:
    """Per-task loop: run an episode under the current strategy, reflect on the
    outcome, and switch strategy when reflection signals it should change.
    """
    if not strategies:
        raise ValueError("strategies must be non-empty")
    current_strategy = strategies[0]
    episodes_run = 0
    for _ in range(max_episodes):
        success = run_episode(current_strategy)
        episodes_run += 1
        if success:
            break
        next_strategy = reflect(success)
        if next_strategy and next_strategy in strategies:
            current_strategy = next_strategy
    return OuterLoopResult(episodes_run=episodes_run, final_strategy=current_strategy)


@dataclass
class MetaLoopResult:
    consolidated: int
    capabilities_evolved: list[str] = field(default_factory=list)


def meta_loop(
    consolidate: Callable[[], int],
    evolve: Callable[[], list[str]],
) -> MetaLoopResult:
    """Long-horizon loop: consolidate accumulated experience, then derive/update
    capabilities (e.g. new combined skills) from what was just consolidated.
    """
    consolidated = consolidate()
    capabilities = evolve()
    return MetaLoopResult(consolidated=consolidated, capabilities_evolved=capabilities)
