# Next Gen Agent — Журнал выполнения плана разработки

> Отдельный файл прогресса. Полный план по фазам — [02_development_plan.md](02_development_plan.md).
> Обновляется по факту завершения каждой фазы/подфазы.

Репозиторий: https://github.com/rusnetru/next-gen-agent

---

## Статус по фазам

| Фаза | Статус | Коммит |
|---|---|---|
| Фаза 0: Фундамент | ✅ Завершена | `db2e386`, `e7aeeae`, `7cafb0d` |
| Фаза 1: Память | ✅ Завершена | `d59ed2a` |
| Фаза 2: Иерархия субагентов | ⬜ Не начата | — |
| Фаза 3: Goal/Loop архитектура | ⬜ Не начата | — |
| Фаза 4: Эволюция и самосовершенствование | ⬜ Не начата | — |
| Фаза 5: Производственная готовность | ⬜ Не начата | — |

---

## Фаза 0: Фундамент — ✅ Завершена

**Цель:** минимальная рабочая архитектура.

### 0.1 Технологический стек — зафиксирован
- LLM backend: Anthropic Claude API
- Векторная БД: ChromaDB (план) / собственный хешированный vector index (текущая реализация) → Qdrant (production)
- Граф памяти: NetworkX → Neo4j (production)
- Оркестрация: собственная реализация (raw SDK, без LangGraph)
- Протоколы: MCP (инструменты) + заглушка A2A
- Язык: Python 3.11+, сборка под Windows (PyInstaller)
- Документ: [03_tech_stack.md](03_tech_stack.md)

### 0.2 Базовый agent loop — реализован
- `src/agent/loop.py` — цикл perceive → retrieve → plan → act → observe → store

### 0.3 Слой памяти v1 — реализован
- `src/memory/working.py` — working memory с FIFO-вытеснением (context window management)
- `src/memory/episodic.py` — episodic store с персистентностью в SQLite
- Авто-консолидация episodic → semantic после N эпизодов

### Результат
- Создан GitHub-репозиторий `rusnetru/next-gen-agent`
- Структура проекта: `docs/`, `src/{agent,memory,orchestrator,tools}/`, `tests/`
- `build.ps1` — сборка Windows exe через PyInstaller
- 10/10 тестов проходят

---

## Фаза 1: Память — ✅ Завершена

**Цель:** полноценная четырёхуровневая система памяти.

### 1.1 Episodic Memory Engine
- Захват событий с метаданными: `timestamp`, `context`, `who`, `where`, `why` (`src/memory/episodic.py`)
- Single-shot learning — эпизод доступен для retrieval сразу после `store()`, без gradient updates
- Hybrid retrieval: `src/memory/vector_index.py` (хешированные bag-of-words эмбеддинги, offline) + keyword match. Точка замены на ChromaDB-эмбеддинги для production — без изменения интерфейса `VectorIndex`

### 1.2 Memory Consolidation Pipeline
- Периодическое сжатие episodic → semantic: `Memory.consolidate()`, авто-триггер по параметру `consolidate_every`
- Вытеснение старых/малорелевантных воспоминаний: `EpisodicMemory.forget_before()` / `Memory.forget()`
- Версионирование памяти (SSGM-inspired): `SemanticGraph.update_fact()` — новая версия факта через `supersedes`-связь, старый факт не удаляется; `history()` восстанавливает цепочку версий

### 1.3 Procedural Memory Store
- Хранение успешных паттернов действий как Skills (`src/memory/skills.py`)
- Автоматическое извлечение Skills из эпизодов: `Memory.skill_extract()`
- Самосовершенствование Skills (Hermes-inspired): `SkillStore.combine()` — сборка составного skill из двух валидированных; ранжирование по `success_rate`

### 1.4 Memory API
```python
memory.store(event, type="episodic", context={...}, who=..., where=..., why=...)
memory.retrieve(query, top_k=5, types=["episodic", "semantic"])
memory.consolidate()        # episodic → semantic
memory.skill_extract(episode_id)
memory.forget(cutoff_timestamp)
```

### Результат
- 17/17 тестов проходят
- Новые файлы: `src/memory/vector_index.py`, тесты `test_episodic_engine.py`, `test_semantic_versioning.py`, `test_skill_store.py`

---

## Известные технические заметки

- В исходном файле `token github.txt` на Desktop был обнаружен GitHub PAT в открытом виде — он не коммитился в репозиторий. Рекомендация: отозвать и сгенерировать новый токен.
- `*.db` (включая `memory.db`) исключены через `.gitignore` — персистентная память не попадает в git.

## Следующий шаг

Фаза 2: Orchestrator Agent + иерархия субагентов (Researcher, Executor, Verifier, Planner, Memory Curator), динамическая топология команды.
