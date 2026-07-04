# Mayya — автономный AI-агент

[![tests](https://img.shields.io/badge/tests-146%2F146-brightgreen)]()
[![evals](https://img.shields.io/badge/evals-8%2F8-brightgreen)]()
[![python](https://img.shields.io/badge/python-3.11+-blue)]()
[![llm](https://img.shields.io/badge/LLM-DeepSeek-6366f1)]()

**Mayya** — автономный AI-агент с 4-уровневой памятью, инструментами и самообучением. Работает в терминале, говорит по-русски.

---

## Быстрый старт

```bash
git clone https://github.com/rusnetru/agent-mayya.git
cd next-gen-agent
powershell .\install.ps1
```

Создай `.env` с ключом DeepSeek:
```
DEEPSEEK_API_KEY=sk-...
```

Запуск:
```bash
python src/main.py
```

---

## Что умеет

| Возможность | Как работает |
|-------------|-------------|
| Веб-поиск | Цепочка провайдеров: Serper/Google → Yandex → DuckDuckGo |
| Чтение страниц | web_extract — загрузка и текст любой страницы |
| Файлы | Чтение, запись, точечная правка (edit_file), regex-поиск (search_files) |
| Терминал | run_command — shell-команды (git, pip, скрипты) |
| Python | Выполнение кода в subprocess |
| Память | 4 уровня: working → episodic → semantic → procedural + инструмент remember |
| Навыки | Папка `skills/` со SKILL.md — Mayya читает их сама по задаче |
| Браузер | Playwright MCP (headless Chrome): навигация, клики, формы, скриншоты |
| GitHub | GitHub MCP: репозитории, коммиты, issues, PR |
| Расписание | cronjob: 'every 10m', 'daily 09:00', 'in 30m' — фоновый раннер выполняет задачи |
| Под-агенты | delegate_task — самостоятельные подзадачи в отдельном контексте |
| MCP | Свой MCP-клиент (stdio) — любой MCP-сервер подключается через `mcp.json` |
| Стриминг | Ответ печатается по мере генерации, инструменты — строками статуса |
| Длинные диалоги | Сжатие контекста: раннее сворачивается в конспект, ничего не теряется |
| Telegram | `--telegram`: полный диалог + cron-дайджесты в чат (нужен свой бот) |
| Evals | `python -m evals.run` — 8 сценариев качества, базовая линия 8/8 |
| Самообучение | SkillEvolutionEngine — авто-извлечение навыков |
| Безопасность | Карантин фактов, approval gate для критических действий |

## Архитектура

Два пути выполнения:

```
Диалог (основной путь):
  ConversationalAgent — живой agent loop:
    история сообщений → recall памяти → LLM ↔ инструменты (до 12 шагов) → ответ
    → эпизод сохраняется в память

Сложные задачи (/task):
  run() → TaskGraph (SQLite) → Orchestrator (LLM-декомпозиция)
    → inner_loop (retry) → [Researcher | Executor | Verifier]
    → outer_loop (reflect) → meta_loop (consolidate + evolve)
    → close() → semantic_graph.json
```

- **Память:** SQLite + ChromaDB (embeddings) + NetworkX (semantic graph)
- **LLM:** DeepSeek (`deepseek-chat`)
- **Интерфейс:** Rich-терминал (цвета, панели, спиннер)
- **Тесты:** 146/146 (pytest) · **Evals:** 8/8

## Команды в интерфейсе

| Команда | Действие |
|---------|----------|
| любое сообщение | Живой диалог с инструментами и памятью |
| `/task <задача>` | Прогнать задачу через оркестратор (subagent-команда) |
| `/help` | Справка |
| `/status` | Память и сессия |
| `exit` / `Ctrl+C` | Выход с сохранением |

## Файлы

| Файл | Назначение |
|------|-----------|
| `memory.db` | Эпизодическая память (SQLite) |
| `tasks.db` | Граф задач |
| `semantic_graph.json` | Семантический граф (сохраняется при выходе) |
| `soul.md` | Базовые правила безопасности |
| `AGENTS.md` | Инструкция для AI-агентов |

## Разработка

```bash
.venv\Scripts\python -m pytest -q    # тесты
python src/main.py                   # запуск
powershell .\update.ps1              # обновление из git
```

## Лицензия

MIT
