"""Telegram-канал Mayya — long polling через Bot API, чистый urllib (без зависимостей).

Настройка (.env):
  TELEGRAM_BOT_TOKEN     — токен собственного бота Mayya от @BotFather (обязателен;
                           НЕ переиспользуй токен бота Hermes — два long-polling
                           клиента на одном токене конфликтуют)
  TELEGRAM_ALLOWED_USERS — id пользователей через запятую (пусто = отвечать всем,
                           не рекомендуется)

Запуск: python -m src.main --telegram
Cron-задачи в этом режиме шлют результат в последний активный чат.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request

API_BASE = "https://api.telegram.org"
MAX_MESSAGE_LEN = 4096
POLL_TIMEOUT = 50


class TelegramChannel:
    """Thin Bot API wrapper. `transport` is injectable for tests."""

    def __init__(self, token: str, allowed_users: set[str] | None = None, transport=None) -> None:
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is empty")
        self.token = token
        self.allowed_users = allowed_users or set()
        self._transport = transport or self._http_call
        self.offset = 0
        self.last_chat_id: int | None = None

    @classmethod
    def from_env(cls) -> "TelegramChannel":
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        users = {
            u.strip()
            for u in os.environ.get("TELEGRAM_ALLOWED_USERS", "").split(",")
            if u.strip()
        }
        return cls(token, allowed_users=users)

    # ── Bot API ───────────────────────────────────────────────

    def _http_call(self, method: str, params: dict, timeout: int) -> dict:
        url = f"{API_BASE}/bot{self.token}/{method}"
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def get_me(self) -> dict:
        return self._transport("getMe", {}, 15).get("result", {})

    def poll_messages(self) -> list[dict]:
        """One long-poll cycle → [{chat_id, user_id, username, text}] from allowed users."""
        data = self._transport(
            "getUpdates",
            {"offset": self.offset, "timeout": POLL_TIMEOUT, "allowed_updates": '["message"]'},
            POLL_TIMEOUT + 10,
        )
        messages: list[dict] = []
        for update in data.get("result", []):
            self.offset = max(self.offset, update["update_id"] + 1)
            msg = update.get("message") or {}
            text = msg.get("text", "")
            chat_id = msg.get("chat", {}).get("id")
            user = msg.get("from", {}) or {}
            user_id = str(user.get("id", ""))
            if not (text and chat_id):
                continue
            if self.allowed_users and user_id not in self.allowed_users:
                continue  # чужих игнорируем молча
            self.last_chat_id = chat_id
            messages.append({
                "chat_id": chat_id,
                "user_id": user_id,
                "username": user.get("username", ""),
                "text": text,
            })
        return messages

    def send_message(self, chat_id: int, text: str) -> None:
        text = text.strip() or "(пустой ответ)"
        for i in range(0, len(text), MAX_MESSAGE_LEN):
            self._transport(
                "sendMessage",
                {"chat_id": chat_id, "text": text[i : i + MAX_MESSAGE_LEN]},
                30,
            )

    def send_typing(self, chat_id: int) -> None:
        try:
            self._transport("sendChatAction", {"chat_id": chat_id, "action": "typing"}, 10)
        except Exception:
            pass  # чисто косметика


def run_telegram_loop(channel: TelegramChannel, agent, on_message=None, stop=None) -> None:
    """Main serving loop: poll → agent.chat → reply. Runs until stop.is_set()."""
    while stop is None or not stop.is_set():
        try:
            messages = channel.poll_messages()
        except Exception as e:
            if on_message:
                on_message(f"[poll error: {e}]")
            time.sleep(3)  # не молотить API при системной ошибке
            continue
        for m in messages:
            if on_message:
                on_message(f"{m['username'] or m['user_id']}: {m['text'][:80]}")
            channel.send_typing(m["chat_id"])
            try:
                reply = agent.chat(m["text"])
            except Exception as e:
                reply = f"Ошибка: {e}"
            channel.send_message(m["chat_id"], reply)
