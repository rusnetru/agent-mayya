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
DEFAULT_MODEL = "deepseek-reasoner"


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
        on_delta=None,
    ) -> dict:
        """Send a request with function-calling tools. Returns dict with 'content' and optional 'tool_calls'.

        If messages is provided, it's used directly (system_prompt/user_message are ignored).
        If on_delta is provided, the response is streamed: on_delta(text_fragment) is
        called as text arrives; the returned dict has the same shape as non-streaming.
        """
        if messages:
            msgs = messages
        else:
            msgs = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]
        if on_delta is not None:
            stream = self._client.chat.completions.create(
                model=self.model,
                temperature=temperature,
                messages=msgs,
                tools=tools,
                tool_choice="auto",
                stream=True,
            )
            return assemble_stream(stream, on_delta)

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


def assemble_stream(chunks, on_delta) -> dict:
    """Fold a streamed chat completion into the non-streaming result shape.

    Text deltas are forwarded to on_delta as they arrive. Tool-call fragments
    (id/name arrive once, arguments drip in pieces) are stitched by index.
    """
    content_parts: list[str] = []
    tool_calls: dict[int, dict] = {}

    for chunk in chunks:
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            continue  # usage/keep-alive chunk
        delta = choices[0].delta
        if delta is None:
            continue
        text = getattr(delta, "content", None)
        if text:
            content_parts.append(text)
            on_delta(text)
        for tc in getattr(delta, "tool_calls", None) or []:
            slot = tool_calls.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
            if getattr(tc, "id", None):
                slot["id"] = tc.id
            fn = getattr(tc, "function", None)
            if fn is not None:
                if getattr(fn, "name", None):
                    slot["name"] = fn.name
                if getattr(fn, "arguments", None):
                    slot["arguments"] += fn.arguments

    result: dict = {"content": "".join(content_parts)}
    if tool_calls:
        result["tool_calls"] = [tool_calls[i] for i in sorted(tool_calls)]
    return result
