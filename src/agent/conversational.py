"""Conversational agent core — the main path for dialog with Mayya.

One live loop instead of the task pipeline: the full message history goes to
the model as real chat messages, the model decides which tools to call, tool
results feed back in, and the loop repeats until the model answers in text.
Episodic memory is recalled into the system prompt before each turn and the
finished exchange is stored back, so Mayya remembers across sessions.

The orchestrator/subagent pipeline (EndToEndAgent) stays for explicitly
delegated complex tasks; it is no longer in the path of every message.
"""

from __future__ import annotations

import datetime
import json
import os

from src.llm.personality import MAYYA_IDENTITY

MAX_TOOL_STEPS = 12          # tool-calling iterations per user message
MAX_HISTORY_MESSAGES = 30    # persistent user/assistant messages kept
TOOL_RESULT_LIMIT = 10_000   # chars of a tool result fed back to the model
MEMORY_RECALL_TOP_K = 3

_FINISH_PROMPT = (
    "Хватит вызывать инструменты. Дай итоговый ответ пользователю на основе того, "
    "что уже нашла. Если чего-то не хватает — честно скажи, что успела выяснить."
)


class ConversationalAgent:
    """LLM-driven dialog loop with tools and memory recall."""

    def __init__(self, client, memory=None, tools: dict | None = None,
                 allow_delegate: bool = True) -> None:
        self.client = client
        self.memory = memory
        if tools is None:
            from src.tools.registry import REGISTRY
            tools = REGISTRY
        self._tools = dict(tools)
        self._tools.pop("delegate_task", None)
        if memory is not None:
            self._tools["remember"] = _make_remember_tool(memory)
        if allow_delegate and self._tools:
            self._tools["delegate_task"] = _make_delegate_tool(client, self._tools)
        # Persistent history: only user/assistant text messages. Tool exchanges
        # live inside a single chat() call so history never has orphan tool ids.
        self.messages: list[dict] = []

    # ── public API ────────────────────────────────────────────

    def chat(self, user_message: str) -> str:
        """Run one dialog turn: recall memory, loop tools, remember the exchange."""
        self.messages.append({"role": "user", "content": user_message})

        turn: list[dict] = [
            {"role": "system", "content": self._system_prompt(user_message)},
            *self.messages,
        ]

        reply = self._tool_loop(turn)

        self.messages.append({"role": "assistant", "content": reply})
        self._trim_history()
        self._remember(user_message, reply)
        return reply

    def reset(self) -> None:
        self.messages.clear()

    # ── internals ─────────────────────────────────────────────

    def _tool_loop(self, turn: list[dict]) -> str:
        from src.tools.registry import get_tool_schemas
        schemas = get_tool_schemas(self._tools)

        for _ in range(MAX_TOOL_STEPS):
            resp = self.client.complete_with_tools(
                system_prompt="", user_message="", tools=schemas, messages=turn,
            )
            tool_calls = resp.get("tool_calls")
            if not tool_calls:
                return resp.get("content", "")

            turn.append({
                "role": "assistant",
                "content": resp.get("content") or "",
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["arguments"]},
                    }
                    for tc in tool_calls
                ],
            })
            for tc in tool_calls:
                turn.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": self._execute(tc)[:TOOL_RESULT_LIMIT],
                })

        # Step budget exhausted — force a text answer from what was gathered.
        turn.append({"role": "user", "content": _FINISH_PROMPT})
        resp = self.client.complete_with_tools(
            system_prompt="", user_message="", tools=schemas, messages=turn,
        )
        return resp.get("content", "")

    def _execute(self, tool_call: dict) -> str:
        name = tool_call["name"]
        tool = self._tools.get(name)
        if tool is None:
            return f"Unknown tool: {name}"
        try:
            args = json.loads(tool_call.get("arguments") or "{}")
            if not isinstance(args, dict):
                args = {}
        except json.JSONDecodeError:
            args = {}
        try:
            return tool.run(**args)
        except Exception as e:
            return f"Error: {e}"

    def _system_prompt(self, user_message: str) -> str:
        from src.skills.loader import skills_prompt

        parts = [
            MAYYA_IDENTITY,
            f"СЕЙЧАС: {datetime.datetime.now():%Y-%m-%d %H:%M}, рабочая папка: {os.getcwd()}",
        ]
        skills = skills_prompt()
        if skills:
            parts.append(skills)
        recalled = self._recall(user_message)
        if recalled:
            parts.append(
                "ПАМЯТЬ (эпизоды из прошлых диалогов, используй если относятся к делу):\n" + recalled
            )
        return "\n\n".join(parts)

    def _recall(self, query: str) -> str:
        if self.memory is None:
            return ""
        try:
            episodes = self.memory.retrieve(query, top_k=MEMORY_RECALL_TOP_K).get("episodic", [])
        except Exception:
            return ""
        lines = []
        for ep in episodes:
            content = getattr(ep, "content", str(ep)).strip()
            if content:
                lines.append(f"- {content[:300]}")
        return "\n".join(lines)

    def _remember(self, user_message: str, reply: str) -> None:
        if self.memory is None or not reply:
            return
        try:
            self.memory.store(
                f"Диалог. User: {user_message[:200]} → Mayya: {reply[:300]}",
                context={"channel": "dialog"},
            )
        except Exception:
            pass  # memory failures must never break the dialog

    def _trim_history(self) -> None:
        if len(self.messages) > MAX_HISTORY_MESSAGES:
            del self.messages[: len(self.messages) - MAX_HISTORY_MESSAGES]
            # never start history with an assistant message
            while self.messages and self.messages[0]["role"] != "user":
                del self.messages[0]


def _make_remember_tool(memory):
    """Explicit long-term memory tool (аналог memory add из Hermes)."""
    from src.tools.registry import Tool

    def remember(fact: str) -> str:
        try:
            memory.store(
                fact,
                type="semantic",
                context={"source": "remember_tool", "confidence": 0.9},
            )
            return json.dumps({"success": True, "stored": fact}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    return Tool(
        name="remember",
        description=(
            "Сохранить важный факт в долговременную память (имя пользователя, "
            "предпочтения, договорённости, важные детали проекта). "
            "Вызывай, когда пользователь просит запомнить или сообщает то, "
            "что пригодится в будущих сессиях."
        ),
        fn=remember,
        parameters={"fact": {"type": "string", "description": "факт для запоминания, одним предложением"}},
    )


def _make_delegate_tool(client, parent_tools: dict):
    """Sub-agent tool (передовая практика: fan-out на под-агентов).

    Под-агент получает те же инструменты, но без delegate_task — глубина
    делегирования ровно один уровень, без рекурсии. Своя история, без памяти:
    результат возвращается родителю, который сам решает, что запомнить.
    """
    from src.tools.registry import Tool

    def delegate_task(task: str) -> str:
        sub_tools = {k: v for k, v in parent_tools.items() if k != "delegate_task"}
        sub = ConversationalAgent(client, memory=None, tools=sub_tools, allow_delegate=False)
        try:
            return sub.chat(task)
        except Exception as e:
            return f"Sub-agent error: {e}"

    return Tool(
        name="delegate_task",
        description=(
            "Делегировать самостоятельную подзадачу под-агенту (свой контекст, те же "
            "инструменты) и получить готовый результат. Используй для объёмных "
            "независимых кусков работы: собрать данные по одной из нескольких тем, "
            "изучить большой файл, проверить гипотезу — пока сама держишь общую картину."
        ),
        fn=delegate_task,
        parameters={"task": {"type": "string", "description": "полная постановка подзадачи со всем нужным контекстом"}},
    )
