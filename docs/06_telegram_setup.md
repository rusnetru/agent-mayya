# Telegram Setup — инструкция для AI-агента

> **Для кого:** AI-агент (DeepSeek/Claude), выполняющий настройку.
> **Для пользователя:** передать токен бота — всё остальное делает агент.

---

## 1. Что нужно от пользователя

Пользователь должен:

1. Написать [@BotFather](https://t.me/BotFather) в Telegram
2. Отправить команду `/newbot`
3. Придумать имя и username бота (например, `NextGenAgentBot`)
4. Получить токен вида `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`
5. Передать этот токен агенту

**Больше от пользователя ничего не требуется.**

---

## 2. Что делает агент (пошагово)

### Шаг 1: Принять токен

Пользователь говорит: «вот токен: `1234567890:ABCdef...`»

Агент сохраняет его:
```python
# Сохранить в .env (если файл существует)
import os
env_path = ".env"
token = "1234567890:ABCdef..."  # получен от пользователя

# Прочитать существующий .env
lines = []
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        lines = f.readlines()

# Заменить или добавить TELEGRAM_BOT_TOKEN
found = False
for i, line in enumerate(lines):
    if line.startswith("TELEGRAM_BOT_TOKEN="):
        lines[i] = f"TELEGRAM_BOT_TOKEN={token}\n"
        found = True
        break
if not found:
    lines.append(f"TELEGRAM_BOT_TOKEN={token}\n")

with open(env_path, "w") as f:
    f.writelines(lines)
```

### Шаг 2: Установить python-telegram-bot

```bash
# В venv проекта
.venv/Scripts/pip install python-telegram-bot
```

И добавить в `requirements.txt` если ещё нет:
```
python-telegram-bot>=20.0
```

### Шаг 3: Создать модуль Telegram-бота

Создать файл `src/telegram_bot.py`:

```python
"""Telegram Bot interface for Next Gen Agent."""

import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from src.agent.end_to_end import EndToEndAgent


class TelegramAgent:
    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN not set — pass token or set in .env")
        self.agent = EndToEndAgent(use_llm=bool(os.environ.get("DEEPSEEK_API_KEY")))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("Next Gen Agent готов. Отправь задачу.")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        task = update.message.text
        await update.message.chat.send_action("typing")
        try:
            result = self.agent.run(task)
            status = "OK" if result.succeeded else "FAIL"
            reply = f"[{status}] strategy={result.strategy} attempts={result.attempts}"
            for line in result.orchestration.get("transcript", [])[:5]:
                reply += f"\n  {line}"
        except Exception as e:
            reply = f"ERROR: {e}"
        await update.message.reply_text(reply)

    def run(self):
        app = Application.builder().token(self.token).build()
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        print(f"Telegram bot starting... @{app.bot.username}" if app.bot else "Telegram bot starting...")
        app.run_polling()
```

### Шаг 4: Точка входа

Создать `run_tg.bat` в корне проекта:

```bat
@echo off
call .venv\Scripts\activate
python -m src.telegram_bot
```

Или добавить в `src/main.py` выбор режима:

```python
if len(sys.argv) > 1 and sys.argv[1] == "--telegram":
    from src.telegram_bot import TelegramAgent
    TelegramAgent().run()
else:
    main()  # CLI-режим
```

### Шаг 5: Запустить и проверить

```bash
python src/main.py --telegram
```

Или:
```bash
run_tg.bat
```

Агент должен ответить:
```
Telegram bot starting... @NextGenAgentBot
```

### Шаг 6: Сообщить пользователю

Агент сообщает:
- Имя бота: `@NextGenAgentBot`
- Ссылка: `https://t.me/NextGenAgentBot`
- Статус: работает

---

## 3. Что проверять при ошибках

| Симптом | Причина | Действие |
|---------|---------|----------|
| `TELEGRAM_BOT_TOKEN not set` | Токен не в `.env` | Повторить шаг 1 |
| `Conflict: terminated by other getUpdates request` | Два процесса опрашивают бота | Убить старый процесс |
| `Forbidden: bot was blocked by the user` | Пользователь заблокировал бота | `/start` в чате с ботом |
| `NetworkError` | Нет интернета или VPN | Проверить соединение |
| `Timed out` | Telegram API недоступен | Подождать, повторить |

---

## 4. Как агент узнаёт, что делать

Агент загружает этот документ при запросе пользователя «настрой Telegram» или «подключи бота». Алгоритм:

1. Запросить у пользователя токен (если ещё не передан)
2. Сохранить в `.env`
3. `pip install python-telegram-bot`
4. Создать `src/telegram_bot.py` по шаблону выше
5. Создать `run_tg.bat`
6. Запустить `python src/main.py --telegram`
7. Сообщить пользователю имя бота и ссылку

---

## 5. Конфигурация (что менять не нужно)

- Порт: не требуется (long polling)
- Webhook: не используется (polling проще, не требует домена/SSL)
- База данных: `memory.db` и `tasks.db` — общие с CLI-режимом
- Групповые чаты: по умолчанию бот не читает группы (нужен `/setprivacy` у BotFather)
