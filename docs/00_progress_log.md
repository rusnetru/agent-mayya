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
| Фаза 2: Иерархия субагентов | ✅ Завершена | `bb06d76` |
| Фаза 3: Goal/Loop архитектура | ✅ Завершена | `a44f961` |
| Фаза 4: Эволюция и самосовершенствование | ✅ Завершена | `ea4bded` |
| Фаза 5: Производственная готовность | 🟡 Частично завершена (всё, что не требует инфраструктуры) | `d0ca38e` |

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

## Фаза 2: Иерархия субагентов — ✅ Завершена

**Цель:** Оркестратор + пул специализированных субагентов.

### 2.1 Orchestrator Agent
- Декомпозиция задачи: `Orchestrator.decompose()` (делегирует `Planner.decompose()`, пока — наивный сплит по " and ")
- Выбор и инициализация субагентов: `Orchestrator.route()` — маршрутизация подзадачи к роли по ключевым словам
- Сборка и верификация результатов: после исполнения всегда запускаются `Verifier` и `MemoryCurator`, итог собирается в `transcript`
- Паттерны исполнения: `sequential` (цикл), `parallel` (`ThreadPoolExecutor`), `hierarchical` (рекурсивная декомпозиция подзадач)

### 2.2 Базовые субагенты (`src/orchestrator/subagents.py`)
- **Researcher** — заглушка поиска/синтеза информации, пишет в `SharedContext`
- **Executor** — заглушка выполнения действия
- **Verifier** — проверяет, что в `SharedContext` появился результат
- **Planner** — декомпозиция задачи на подзадачи
- **Memory Curator** — пишет эпизод в episodic memory и запускает консолидацию (использует Memory API из Фазы 1)

### 2.3 Динамическая топология
- `Orchestrator.pool` — реестр `role -> Subagent`, не фиксирован на этапе конструирования
- `register(role, agent)` / `unregister(role)` — добавление/удаление типов субагентов в рантайме
- Маршрутизация по ключевым словам легко расширяется новыми ролями без изменения ядра оркестратора

### 2.4 Subagent Communication Layer (`src/orchestrator/communication.py`)
- `SharedContext` — общая working memory команды на время одного запуска: `data` (key/value) + `transcript` (append-only лог сообщений агентов)
- Структура задумана как нейтральный payload, пригодный для A2A-совместимой внешней интеграции в будущем (сам протокол A2A — вне рамок Фазы 2)

### Результат
- Новые файлы: `src/orchestrator/communication.py`, `src/orchestrator/subagents.py`, `src/orchestrator/orchestrator.py`, `tests/test_orchestrator.py`
- 28/28 тестов проходят (11 новых)

---

## Фаза 3: Goal/Loop архитектура — ✅ Завершена

**Цель:** автоматическое планирование и самокоррекция.

### 3.1 Goal Management System (`src/goals/goal_stack.py`)
- Иерархия целей с горизонтами `long_term → mid_term → task → action`
- `GoalStack.decompose()` — автоматическая декомпозиция на один горизонт глубже
- `GoalStack.revise()` — пересмотр описания/активности цели при изменении контекста
- `active_leaves()` — какие именно цели сейчас актуальны для работы (без активных детей)

### 3.2 Planning Engine (`src/planning/engine.py`)
- Базовый: `react_with_self_critique()` — ReAct-цикл с self-critique (Reflexion-style), ретраи с фидбеком до прохождения критики или исчерпания бюджета попыток
- Расширенный: `mcts_select_action()` — упрощённый MCTS (UCB1, симуляции с наградой) для выбора действия среди вариантов (LATS-inspired)
- Мета: `StrategyRegistry` — учёт успешности стратегий по классам задач, выбор лучшей стратегии на основе истории (TodoEvolve-inspired); для неизвестного класса задачи — нейтральный приоритет (50/50)

### 3.3 Task-Decoupled Execution (`src/tasks/task_graph.py`)
- `TaskGraph` — план («что делать») отделён от исполнения («как делать сейчас» — передаётся вызывающей стороной в `run_ready(execute)`)
- Персистентность в SQLite — незавершённые задачи переживают перезапуск процесса (аналогично `EpisodicMemory`)
- DAG: зависимости между задачами (`depends_on`), `ready_tasks()` возвращает независимые ветки, пригодные для параллельного исполнения

### 3.4 Self-Correction Loops (`src/loops/self_correction.py`)
- `inner_loop(act, verify, max_retries)` — per-action: действие → проверка → повтор
- `outer_loop(run_episode, reflect, strategies)` — per-task: эпизод → рефлексия → смена стратегии при неудаче
- `meta_loop(consolidate, evolve)` — долгосрочный: консолидация опыта → развитие способностей
- Все три — универсальные драйверы над callable-аргументами, не привязаны к конкретной реализации Orchestrator/Memory/Planning Engine

### Результат
- Новые директории: `src/goals/`, `src/planning/`, `src/tasks/`, `src/loops/`
- Новые тесты: `test_goal_stack.py`, `test_planning_engine.py`, `test_task_graph.py`, `test_self_correction_loops.py`
- 49/49 тестов проходят (21 новый)

---

## Фаза 4: Эволюция и самосовершенствование — ✅ Завершена

**Цель:** агент улучшает себя в процессе работы, не переписывая собственный код.

### 4.1 Skill Evolution Engine (`src/evolution/skill_evolution.py`)
- `extract_from_successful_episodes()` — сканирует episodic-эпизоды с `context["success"] == True` и автоматически создаёт/обновляет Skills через `Memory.skill_extract()`
- `rank()` — ранжирование Skills по `success_rate`, затем по числу использований
- `auto_combine_sequential_pairs()` — находит пары навыков, повторяющиеся подряд в успешных эпизодах не реже `min_co_occurrences` раз, и автоматически собирает их в составной skill через `SkillStore.combine()`

### 4.2 Strategy Adaptation (`src/evolution/strategy_adaptation.py`)
- `StrategyAdapter` — тонкая обёртка над `StrategyRegistry` (Фаза 3): `select(task_class)` выбирает зарегистрированную стратегию по истории успеха, `observe()` пишет исход
- Адаптация ограничена выбором *имени* стратегии — агент не генерирует и не подменяет код, только конфигурацию (явное отличие от self-rewriting подходов вроде Hyperagents)

### 4.3 Team Composition Learning (`src/evolution/team_composition.py`)
- `TeamCompositionLearner.record(task_class, team, success)` — фиксирует исход для конкретной комбинации ролей субагентов
- `best_team(task_class)` — возвращает состав команды с наивысшим success rate для класса задач
- История пишется как факты в `SemanticGraph` (`team[task_class] = role1+role2`, метаданные `uses`/`successes`) — переживает консолидацию памяти из Фазы 1

### Результат
- Новая директория: `src/evolution/`
- Новые тесты: `test_skill_evolution.py`, `test_strategy_adaptation.py`, `test_team_composition.py`
- `SkillStore` дополнен публичным `all()` вместо доступа к приватному полю
- 58/58 тестов проходят (9 новых)

---

## Фаза 5: Производственная готовность — 🟡 Частично завершена

**Цель:** надёжность, наблюдаемость, масштабируемость. Реализовано всё, что укладывается в библиотечный код этого репозитория; пункты, требующие реальной инфраструктуры (деплой, облачная БД), осознанно не реализовывались как код — см. ниже.

### 5.1 Observability — завершено
- `Tracer` (`src/observability/tracer.py`) — структурированные trace-события (component/action/data/timestamp), фильтрация по компоненту, экспорт в JSON-совместимый список
- `snapshot()` (`src/observability/dashboard.py`) — единый снимок состояния: working memory, episodic count, рейтинг skills (uses/successes/success_rate), активные цели из `GoalStack`

### 5.2 Safety & Governance — завершено
- `MemorySafetyGuard` (`src/safety/memory_guard.py`, SSGM-inspired) — факты с низкой confidence или прямым противоречием существующему факту уходят в карантин (`quarantine`), а не сразу в semantic memory; `release()` — ручной override оператором
- `HumanApprovalGate` (`src/safety/governance.py`) — критические действия (по списку) ставятся в очередь `pending`, требуют explicit `approve()`/`reject()`
- `SelfModificationPolicy` — адаптация конфигурации (Фаза 4.2) ограничена явным списком разрешённых ключей; попытка изменить что-то ещё — `PermissionError`

### 5.3 Scalability — частично
- `run_async()` (`src/scalability/async_execution.py`) — асинхронный (`asyncio`) эквивалент параллельного исполнения субагентов из Orchestrator
- **Не реализовано (требует инфраструктуры, не кода):** horizontal scaling оркестратора (нужен реальный деплой нескольких процессов/нод + балансировка); distributed memory / переход SQLite → cloud vector DB (нужно поднять внешнюю БД, например Qdrant/Neo4j из `docs/03_tech_stack.md`). Текущие интерфейсы (`Memory`, `EpisodicMemory`, `SemanticGraph`) спроектированы так, чтобы backend можно было заменить без изменения контракта — сама миграция остаётся будущей задачей при появлении реальной инфраструктуры.

### Результат
- Новые директории: `src/observability/`, `src/safety/`, `src/scalability/`
- Новые тесты: `test_observability.py`, `test_safety.py`, `test_async_execution.py`
- 70/70 тестов проходят (12 новых)
- Windows-сборка проверена: `python -m PyInstaller --onefile --name next-gen-agent src/main.py` собрал рабочий `dist\next-gen-agent.exe` (~231 МБ, тянет torch/onnxruntime через chromadb), запуск подтверждён — exe выполнил agent loop (`[stub action] respond to: hello`) и создал персистентную `memory.db` рядом с собой

---

## Известные технические заметки

- В исходном файле `token github.txt` на Desktop был обнаружен GitHub PAT в открытом виде — он не коммитился в репозиторий. Рекомендация: отозвать и сгенерировать новый токен.
- `*.db` (включая `memory.db`, `tasks.db`) исключены через `.gitignore` — персистентные данные не попадают в git.
- Subagents в Фазе 2 — детерминированные заглушки (без вызовов LLM), чтобы оркестрация (декомпозиция, маршрутизация, коммуникация) тестировалась без сети. Подключение реального Claude API внутрь `act()` — следующий технический шаг, не меняющий контракт `Orchestrator`.
- Goal Stack, Planning Engine, Task Graph, Self-Correction Loops (Фаза 3), весь Evolution-слой (Фаза 4) и весь Observability/Safety/Scalability-слой (Фаза 5) реализованы как независимые модули поверх Memory/Orchestrator — ещё не связаны друг с другом в единый end-to-end цикл агента.
- Subagents всё ещё детерминированные заглушки — реальный вызов Claude API внутрь `Subagent.act()` не реализован.
- `dist\next-gen-agent.exe` весит ~231 МБ — PyInstaller затягивает в onefile-бандл весь транзитивный вес `chromadb` (включая `torch`, `onnxruntime`), хотя текущий код фактически использует только собственный `vector_index.py`. При необходимости компактной сборки: явно исключить неиспользуемые тяжёлые пакеты через `--exclude-module` в `build.ps1`, либо отложить `chromadb` в requirements до момента реальной интеграции embedding-модели.

## Следующий шаг

Все 6 фаз плана пройдены в объёме, реализуемом как библиотечный код (Фаза 5 — частично, см. выше). Дальнейшая работа — не новая фаза, а **сквозная интеграция**:
1. Связать Orchestrator + Goal Stack + Planning Engine + Task Graph + Self-Correction Loops в единый end-to-end `Agent`-цикл (сейчас это независимые модули)
2. Заменить детерминированные заглушки субагентов на реальные вызовы Claude API
3. Подключить реальную инфраструктуру для оставшихся пунктов Фазы 5.3 (cloud vector DB, horizontal scaling) при появлении production-окружения
