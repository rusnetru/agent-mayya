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
        MAYYA_IDENTITY + "\n\nТы — исследователь Mayya. Твоя задача: найти информацию по запросу пользователя.\n"
        "У тебя есть ИНСТРУМЕНТЫ:\n"
        "- web_search(query) — поиск в интернете (DuckDuckGo)\n"
        "- web_extract(url) — загрузить и прочитать содержимое страницы\n\n"
        "ПОРЯДОК ДЕЙСТВИЙ:\n"
        "1. Сначала вызови web_search по запросу\n"
        "2. Найди релевантный результат и вызови web_extract с его URL\n"
        "3. Проанализируй содержимое страницы и дай краткий ответ\n\n"
        "ВАЖНО: не пиши «я не могу переходить по ссылкам» — ты МОЖЕШЬ, используй web_extract."
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
        self._tools: dict | None = None

    def _ensure_tools(self) -> dict:
        if self._tools is None:
            from src.tools.registry import REGISTRY
            self._tools = REGISTRY
        return self._tools

    def _get_tool_schemas(self) -> list[dict]:
        """Return OpenAI-compatible tool schemas for researcher."""
        from src.tools.registry import get_tool_schemas
        return get_tool_schemas()

    def act(self, task: str, context: SharedContext) -> str:
        system_prompt = _SYSTEM_PROMPTS.get(self.role, f"You are the {self.role} subagent.")

        # For researcher: try tool-calling loop first (web_search → web_extract → analyse)
        if self.role == "researcher":
            return self._act_with_tools(task, context, system_prompt)

        # For other roles: plain text completion
        result = self.client.complete(system_prompt, task)
        context.set(self.context_key, result)
        return result

    def _act_with_tools(self, task: str, context: SharedContext, system_prompt: str) -> str:
        """Agent loop: LLM decides which tools to call, executes them, repeats until done."""
        import json as _json

        tools = self._ensure_tools()
        schemas = self._get_tool_schemas()

        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ]

        for _step in range(5):  # max 5 tool-calling iterations
            resp = self.client.complete_with_tools(
                system_prompt="",  # already in messages
                user_message="",   # already in messages
                tools=schemas,
            )

            # If model returned text without tool calls — done
            if not resp.get("tool_calls"):
                result = resp.get("content", "")
                context.set(self.context_key, result)
                return result

            # Execute tool calls
            for tc in resp["tool_calls"]:
                tool_name = tc["name"]
                try:
                    args = _json.loads(tc["arguments"])
                except _json.JSONDecodeError:
                    args = {}

                if tool_name in tools:
                    try:
                        tool_result = tools[tool_name].run(**args)
                    except Exception as e:
                        tool_result = f"Error: {e}"
                else:
                    tool_result = f"Unknown tool: {tool_name}"

                # Add assistant message with tool call
                messages.append({
                    "role": "assistant",
                    "content": resp.get("content") or "",
                    "tool_calls": [{
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tool_name, "arguments": tc["arguments"]},
                    }],
                })
                # Add tool result
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_result,
                })

        # Fallback: after max steps, ask for final answer
        fallback = self.client.complete(
            system_prompt + "\n\nДай итоговый ответ на основе найденной информации. Будь краток.",
            _json.dumps(messages[-6:], ensure_ascii=False),
        )
        context.set(self.context_key, fallback)
        return fallback


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
