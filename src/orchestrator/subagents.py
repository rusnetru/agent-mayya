"""Base subagent pool (Phase 2.2): Researcher, Executor, Verifier, Planner, Memory Curator.

Each subagent exposes act(task, context) -> str. Implementations are
deterministic stubs (no live LLM calls) so the orchestration logic itself —
decomposition, topology selection, communication — can be exercised and
tested without external dependencies. Swapping a subagent's act() body for a
real Claude API call does not change the Orchestrator contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.memory.api import Memory
from src.orchestrator.communication import SharedContext


class Subagent(ABC):
    role: str = "subagent"

    @abstractmethod
    def act(self, task: str, context: SharedContext) -> str: ...


class Researcher(Subagent):
    role = "researcher"

    def act(self, task: str, context: SharedContext) -> str:
        finding = f"research findings on: {task}"
        context.set("research", finding)
        return finding


class Executor(Subagent):
    role = "executor"

    def __init__(self) -> None:
        self._tools: dict | None = None

    def _ensure_tools(self) -> dict:
        if self._tools is None:
            from src.tools.registry import REGISTRY
            self._tools = REGISTRY
        return self._tools

    def act(self, task: str, context: SharedContext) -> str:
        # Try to parse task as a tool call: "tool_name(arg1=val1, ...)"
        tool_name, args = self._parse_tool_call(task)
        if tool_name and tool_name in self._ensure_tools():
            try:
                result = self._ensure_tools()[tool_name].run(**args)
                context.set("execution_result", result)
                return result
            except Exception as e:
                error = f"tool error [{tool_name}]: {e}"
                context.set("execution_result", error)
                return error

        # Fallback: generic execution
        result = f"executed: {task}"
        context.set("execution_result", result)
        return result

    @staticmethod
    def _parse_tool_call(task: str) -> tuple[str | None, dict]:
        """Parse 'tool_name(key=value, ...)' from task string."""
        import re
        m = re.match(r"(\w+)\((.*)\)", task.strip())
        if not m:
            return None, {}
        tool_name = m.group(1)
        args_str = m.group(2)
        args = {}
        for pair in re.findall(r"(\w+)=([\"'].*?[\"']|\S+)", args_str):
            key, val = pair
            val = val.strip("\"'")
            args[key] = val
        return tool_name, args


class Verifier(Subagent):
    role = "verifier"

    def act(self, task: str, context: SharedContext) -> str:
        has_result = bool(context.get("execution_result") or context.get("research"))
        verdict = "verified: ok" if has_result else "verified: failed (no result to check)"
        context.set("verified", has_result)
        return verdict


class Planner(Subagent):
    role = "planner"

    def act(self, task: str, context: SharedContext) -> str:
        subtasks = self.decompose(task)
        context.set("subtasks", subtasks)
        return f"plan: {subtasks}"

    def decompose(self, task: str) -> list[str]:
        parts = [p.strip() for p in task.split(" and ") if p.strip()]
        return parts or [task]


class MemoryCurator(Subagent):
    role = "memory_curator"

    def __init__(self, memory: Memory) -> None:
        self.memory = memory

    def act(self, task: str, context: SharedContext) -> str:
        self.memory.store(task, context={"orchestrated": True})
        promoted = self.memory.consolidate()
        return f"curated: stored episode, promoted {promoted} fact(s)"
