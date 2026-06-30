"""Async execution of subagents (Phase 5.3).

Complements `Orchestrator`'s thread-based `parallel` pattern with a coroutine
path for I/O-bound subagents (e.g. calling external APIs) where asyncio
concurrency is cheaper than threads. Horizontal scaling of the orchestrator
process itself and a distributed/cloud memory backend are infrastructure
concerns outside this repository's scope — see docs/00_progress_log.md.
"""

from __future__ import annotations

import asyncio

from src.orchestrator.communication import SharedContext
from src.orchestrator.orchestrator import Orchestrator


async def dispatch_async(orchestrator: Orchestrator, subtask: str, context: SharedContext) -> None:
    role = orchestrator.route(subtask)
    agent = orchestrator.pool[role]
    result = await asyncio.to_thread(agent.act, subtask, context)
    context.post(role, result)


async def run_subtasks_async(
    orchestrator: Orchestrator,
    subtasks: list[str],
    context: SharedContext,
) -> None:
    await asyncio.gather(*(dispatch_async(orchestrator, st, context) for st in subtasks))


async def run_async(orchestrator: Orchestrator, task: str) -> dict:
    """Async counterpart of Orchestrator.run(pattern="parallel")."""
    context = SharedContext(task=task)
    subtasks = orchestrator.decompose(task)
    await run_subtasks_async(orchestrator, subtasks, context)

    verdict = orchestrator.pool["verifier"].act(task, context)
    context.post("verifier", verdict)
    curation = orchestrator.pool["memory_curator"].act(task, context)
    context.post("memory_curator", curation)

    return {
        "task": task,
        "subtasks": subtasks,
        "verified": context.get("verified", False),
        "transcript": context.history(),
    }
