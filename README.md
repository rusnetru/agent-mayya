# Mayya — автономный AI-агент

[![tests](https://img.shields.io/badge/tests-101%2F101-brightgreen)]()
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
| Веб-поиск | DuckDuckGo (без API-ключа), два endpoint'а с fallback |
| Чтение страниц | web_extract — загрузка и текст любой страницы |
| Файлы | Чтение, запись, список директорий |
| Python | Выполнение кода в subprocess |
| Память | 4 уровня: working → episodic → semantic → procedural |
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
- **Тесты:** 101/101 (pytest)

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
