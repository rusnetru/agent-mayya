# Telegram Setup — Mayya в Telegram

Реализация: `src/channels/telegram.py` (long polling, чистый urllib) + режим `--telegram` в `src/main.py`.

## Что нужно от пользователя (один раз)

1. Написать [@BotFather](https://t.me/BotFather) → `/newbot` → имя и username бота (например `MayyaAgentBot`)
2. Получить токен вида `1234567890:ABCdef...`
3. Узнать свой Telegram id (напиши боту [@userinfobot](https://t.me/userinfobot))
4. Добавить в `.env` проекта:

```
TELEGRAM_BOT_TOKEN=1234567890:ABCdef...
TELEGRAM_ALLOWED_USERS=123456789
```

**Важно:** токен бота Hermes переиспользовать нельзя — два long-polling клиента
на одном токене конфликтуют (Telegram отдаёт updates только одному).

## Запуск

```bash
.venv\Scripts\python -m src.main --telegram
```

При старте Mayya покажет username бота и список разрешённых пользователей.
Дальше — просто пиши боту в Telegram: полный диалог с инструментами, памятью и навыками.

## Что работает в Telegram-режиме

- Полноценный диалог (все инструменты: поиск, браузер MCP, файлы, терминал, память)
- Ответы длиннее 4096 символов режутся на несколько сообщений
- Cron-задачи шлют результат в последний активный чат — дайджесты приходят в телефон
- Пользователи не из `TELEGRAM_ALLOWED_USERS` игнорируются молча
- Если токен не задан — Mayya печатает инструкцию и не падает

## Ограничения

- Long polling: Mayya должна быть запущена (окно/процесс). Webhook-режим — в бэклоге
- Нет стриминга в Telegram (Bot API не стримит) — вместо этого статус «печатает…»
