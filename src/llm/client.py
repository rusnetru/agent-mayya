"""LLM client (Phase 6 — replacing deterministic subagent stubs with a real model).

DeepSeek exposes an OpenAI-compatible Chat Completions API, so the official
`openai` SDK is reused as the transport — only `base_url` differs. This keeps
the client swappable: pointing `base_url`/`model` elsewhere (or back at
Anthropic) does not change `LLMClient`'s public contract (`complete()`).
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from openai import OpenAI

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"


class LLMClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEEPSEEK_BASE_URL,
        model: str = DEFAULT_MODEL,
    ) -> None:
        load_dotenv()
        resolved_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not resolved_key:
            raise RuntimeError(
                "DEEPSEEK_API_KEY not set — put it in .env or pass api_key explicitly"
            )
        self.model = model
        self._client = OpenAI(api_key=resolved_key, base_url=base_url)

    def complete(self, system_prompt: str, user_message: str, temperature: float = 0.3) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content or ""

    def complete_with_tools(
        self,
        system_prompt: str,
        user_message: str,
        tools: list[dict],
        temperature: float = 0.3,
        messages: list[dict] | None = None,
    ) -> dict:
        """Send a request with function-calling tools. Returns dict with 'content' and optional 'tool_calls'.
        
        If messages is provided, it's used directly (system_prompt/user_message are ignored).
        """
        if messages:
            msgs = messages
        else:
            msgs = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]
        response = self._client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            messages=msgs,
            tools=tools,
            tool_choice="auto",
        )
        msg = response.choices[0].message
        result: dict = {"content": msg.content or ""}
        if msg.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                }
                for tc in msg.tool_calls
            ]
        return result
