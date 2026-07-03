"""LLM-backed subagents — replace the Phase 2 deterministic stubs with real
model calls while keeping the exact same `Subagent.act(task, context) -> str`
contract, so `Orchestrator` needs zero changes to use them.
"""

from __future__ import annotations

from src.llm.client import LLMClient
from src.llm.personality import MAYYA_IDENTITY
from src.memory.api import Memory
from src.orchestrator.communication import SharedContext
from src.orchestrator.subagents import MemoryCurator, Subagent

_SYSTEM_PROMPTS = {
    "researcher": (
        MAYYA_IDENTITY + "\n\nТы — исследователь. Найди информацию по задаче и дай чёткий ответ."
    ),
    "executor": (
        MAYYA_IDENTITY + "\n\nТы — исполнитель. Отвечай текстом, как в обычном диалоге. "
        "Пиши код на Python ТОЛЬКО если тебя явно попросили: «напиши код», «выполни скрипт», «запусти python». "
        "В коде используй ТОЛЬКО валидный синтаксис Python. "
        "Если просят представиться или рассказать о себе — используй факты из секции О СЕБЕ выше. "
        "Не выдумывай архитектуру, не придумывай зависимости."
    ),
}


class LLMSubagent(Subagent):
    """Generic LLM-driven subagent for a given role/context_key/system prompt."""

    def __init__(self, role: str, client: LLMClient, context_key: str) -> None:
        self.role = role
        self.client = client
        self.context_key = context_key

    def act(self, task: str, context: SharedContext) -> str:
        system_prompt = _SYSTEM_PROMPTS.get(self.role, f"You are the {self.role} subagent.")
        result = self.client.complete(system_prompt, task)
        context.set(self.context_key, result)
        return result


class LLMVerifier(Subagent):
    """LLM-driven Verifier: judges whether prior subagent output satisfies the task."""

    role = "verifier"

    _SYSTEM_PROMPT = (
        "Ты Mayya — верификатор. Дана исходная задача и результаты других агентов. "
        "Ответь одним словом: PASS если работа выполнена, FAIL если нет."
    )

    def __init__(self, client: LLMClient) -> None:
        self.client = client

    def act(self, task: str, context: SharedContext) -> str:
        evidence = "\n".join(context.history()) or "(no prior output)"
        user_message = f"Task: {task}\n\nWork so far:\n{evidence}"
        verdict = self.client.complete(self._SYSTEM_PROMPT, user_message)
        passed = "PASS" in verdict.upper()
        context.set("verified", passed)
        return f"verified: {'ok' if passed else 'failed'} ({verdict.strip()})"


def build_llm_subagent_pool(client: LLMClient, memory: Memory) -> dict[str, Subagent]:
    """Researcher/Executor/Verifier/Planner go through the LLM; MemoryCurator stays
    deterministic — memory bookkeeping doesn't need a model call.
    """
    return {
        "researcher": LLMSubagent("researcher", client, context_key="research"),
        "executor": LLMSubagent("executor", client, context_key="execution_result"),
        "verifier": LLMVerifier(client),
        "planner": LLMPlanner(client),
        "memory_curator": MemoryCurator(memory),
    }


class LLMPlanner(Subagent):
    """LLM-driven Planner: decomposes a task into subtasks via the model."""

    role = "planner"

    _SYSTEM_PROMPT = (
        "Ты Mayya — планировщик. Разбей задачу на 2-4 конкретные подзадачи. "
        "Верни ТОЛЬКО JSON-массив строк, ничего больше. "
        'Пример: ["найти цены конкурентов", "написать отчёт"].'
    )

    def __init__(self, client: LLMClient) -> None:
        self.client = client

    def act(self, task: str, context: SharedContext) -> str:
        subtasks = self.decompose(task)
        context.set("subtasks", subtasks)
        return f"plan: {subtasks}"

    def decompose(self, task: str) -> list[str]:
        import json as _json

        try:
            raw = self.client.complete(self._SYSTEM_PROMPT, task)
            parts = _json.loads(raw)
            if isinstance(parts, list) and all(isinstance(p, str) for p in parts):
                return [p for p in parts if p.strip()]
        except Exception:
            pass
        # Fallback: naive split
        parts = [p.strip() for p in task.split(" and ") if p.strip()]
        return parts or [task]
