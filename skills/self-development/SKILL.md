---
name: self-development
description: Работа над собственным кодом Mayya — пути, тесты, git-workflow, как безопасно менять себя. Использовать когда просят улучшить/починить/изучить саму Mayya.
version: 1.0.0
---

# Self Development — работа над собственным проектом

## Карта проекта

- Корень: текущая рабочая папка (репозиторий agent-mayya, GitHub: rusnetru/agent-mayya)
- `src/agent/conversational.py` — основной диалоговый цикл (ты сама)
- `src/tools/` — инструменты и реестр (`registry.py`)
- `skills/` — навыки (этот файл — один из них)
- `src/orchestrator/` — сабагенты для `/task`
- `src/memory/` — 4-уровневая память
- `tests/` — pytest
- `docs/00_progress_log.md` — журнал фаз; `docs/development-report-*.md` — отчёты сессий

## Как менять код безопасно

1. Прочитай нужный файл (read_file), пойми контекст.
2. Правь точечно через edit_file (не перезаписывай файл целиком через write_file).
3. Прогони тесты: `run_command(".venv\\Scripts\\python -m pytest -q")` — все должны пройти.
4. Коммит: `run_command("git add -A && git commit -m \"...\"")`, затем `git push origin main`.
5. Задокументируй заметное изменение в `docs/00_progress_log.md`.

## Ограничения

- Не трогай `.env` (там ключи) и файлы баз (`memory.db`, `tasks.db`) руками.
- Изменение собственного промпта/личности (`src/llm/personality.py`) — только по явной просьбе пользователя.
