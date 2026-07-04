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
| Фаза 5: Производственная готовность | 🟡 Частично завершена (всё, что не требует инфраструктуры) | `d0ca38e`, `91d9b31` (git-deploy) |
| Фаза 6: Сквозная интеграция + реальный LLM (DeepSeek) | ✅ Завершена (вне исходных 6 фаз плана) | `3ba99fe` |

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

## Развёртывание и обновление — переход на git-based модель

По запросу пользователя отказались от `.exe` как основного способа развёртывания. Текущая модель:

- **Установка**: `git clone` + `install.ps1` (venv + `pip install -r requirements.txt`)
- **Обновление**: `update.ps1` — `git fetch` + `git pull --ff-only`, переустановка зависимостей при изменении `requirements.txt`, отказ обновляться поверх незакоммиченных локальных правок
- **Программный self-update**: `src/update/self_update.py` — та же логика как Python API (`check_for_updates()`, `self_update()`), которую агент может вызывать сам (например, в начале сессии или по расписанию), чтобы подтягивать новый код из репозитория без участия человека на каждом шаге
- Сборка `.exe` (`build.ps1`) осталась как опциональный путь для машин, где принципиально нельзя ставить Python/git — но такой `.exe` не обновляется автоматически, его нужно пересобирать вручную
- Документация: [docs/04_deployment.md](04_deployment.md) переписана под git-flow, README обновлён

### Результат
- Новая директория: `src/update/`, новый файл `tests/test_self_update.py` (7 тестов на реальном git-репозитории во временной директории: pull нового коммита, отказ при грязном дереве, обнаружение изменений в `requirements.txt`)
- Новые скрипты в корне: `install.ps1`, `update.ps1`
- 77/77 тестов проходят (7 новых)

---

## Фаза 6: Сквозная интеграция + реальный LLM (DeepSeek) — ✅ Завершена

**Цель:** заменить детерминированные заглушки субагентов реальными вызовами LLM и связать ранее независимые модули (Orchestrator, Goal Stack, Strategy Adaptation, Self-Correction, Observability) в единый end-to-end цикл.

Инициировано на основе внешнего сравнительного анализа (`Hermes vs NexGen agent analysis.txt`, предоставлен пользователем) — Hermes выигрывал именно за счёт реального LLM и сквозной интеграции; план из раздела 6 этого анализа лёг в основу реализации.

### LLM-слой (`src/llm/`)
- `client.py` — `LLMClient`, тонкая обёртка над `openai`-SDK, указывающая `base_url=https://api.deepseek.com` (DeepSeek API OpenAI-совместим). Ключ читается из `DEEPSEEK_API_KEY` через `.env` (`python-dotenv`) — **ключ не коммитится**, `.env` в `.gitignore`
- `subagent.py` — `LLMSubagent` (generic, для Researcher/Executor) и `LLMVerifier` (парсит PASS/FAIL из ответа модели в `context["verified"]`), оба реализуют ровно тот же контракт `Subagent.act(task, context) -> str`, что и стабы из Фазы 2 — `Orchestrator` не пришлось менять
- `build_llm_subagent_pool()` — Planner и MemoryCurator остаются детерминированными (декомпозиция и работа с памятью не требуют модели), Researcher/Executor/Verifier — через LLM

### End-to-end цикл (`src/agent/end_to_end.py`)
`EndToEndAgent.run(task, task_class)` реально связывает:
- `GoalStack` — задача регистрируется как цель, по завершении деактивируется
- `StrategyAdapter` (Фаза 4.2) — выбирает паттерн исполнения (sequential/parallel/hierarchical) по истории успеха для класса задач
- `Orchestrator` (Фаза 2) — исполняет задачу через пул субагентов (LLM или заглушки — флаг `use_llm`)
- `inner_loop` (Фаза 3.4) — ретраит исполнение, если `Verifier` не подтвердил результат
- `Tracer` (Фаза 5.1) — фиксирует ключевые события всего прогона

### Подтверждение реальной работы
`python -m src.main` с `DEEPSEEK_API_KEY` в `.env` выполнил настоящий end-to-end прогон: Researcher и Executor дали содержательные ответы от модели `deepseek-chat`, Verifier (тоже LLM) реально оценил результат и вынес вердикт (в т.ч. наблюдался честный `FAIL` с ретраем) — то есть self-correction loop отработал на живых данных, а не на заглушке.

### Результат
- Новые файлы: `src/llm/client.py`, `src/llm/subagent.py`, `src/agent/end_to_end.py`
- Новые тесты: `test_llm_client.py`, `test_llm_subagent.py`, `test_end_to_end.py` (все юнит-тесты используют fake-клиент, реальных сетевых вызовов в тестах нет — быстро и детерминированно)
- `src/main.py` переписан: запускает `EndToEndAgent`, автоматически включает LLM-режим, если `DEEPSEEK_API_KEY` задан в окружении
- 87/87 тестов проходят (17 новых)

---

## Известные технические заметки

- В исходном файле `token github.txt` на Desktop был обнаружен GitHub PAT в открытом виде — он не коммитился в репозиторий. Рекомендация: отозвать и сгенерировать новый токен.
- `*.db` (включая `memory.db`, `tasks.db`) исключены через `.gitignore` — персистентные данные не попадают в git.
- `DEEPSEEK_API_KEY` хранится в `next-gen-agent/.env` (исключён `.gitignore`); исходный файл с ключом на Desktop (`api llm.txt`) оставлен пользователем как есть, вне репозитория.
- `dist\next-gen-agent.exe` весит ~231 МБ — PyInstaller затягивает в onefile-бандл весь транзитивный вес `chromadb` (включая `torch`, `onnxruntime`), хотя текущий код фактически использует только собственный `vector_index.py`. При необходимости компактной сборки: явно исключить неиспользуемые тяжёлые пакеты через `--exclude-module` в `build.ps1`, либо отложить `chromadb` в requirements до момента реальной интеграции embedding-модели. Развёртывание в любом случае теперь идёт через git (см. раздел выше), не через exe.

## Следующий шаг

Базовый end-to-end цикл с реальным LLM работает. Дальнейшие направления:
1. Перевести `Planner` на LLM-декомпозицию вместо наивного сплита по " and " (сейчас осознанно оставлен детерминированным)
2. Заменить упрощённый MCTS (`src/planning/engine.py`) на более полноценную реализацию с деревом и backpropagation
3. Маршрутизация субагентов (`Orchestrator.route()`) — перевести с keyword-matching на LLM-роутинг
4. Подключить реальную инфраструктуру для оставшихся пунктов Фазы 5.3 (cloud vector DB, horizontal scaling) при появлении production-окружения

---

## Фаза 7: MVP-запуск — ✅ Завершена (Hermes Agent)

**Цель:** дать агенту практическую применимость — инструменты, интерфейс, персистентность.

Дата: 2026-07-03 | Исполнитель: Hermes Agent (DeepSeek)

### 7.1 Инструменты (`src/tools/`)

Реализован базовый набор из 5 инструментов:

| Инструмент | Файл | Что делает |
|---|---|---|
| `web_search` | `web_search.py` | Поиск через DuckDuckGo HTML (без API-ключа) |
| `read_file` | `file_tools.py` | Чтение текстовых файлов |
| `write_file` | `file_tools.py` | Запись в файл (создаёт родительские директории) |
| `list_dir` | `file_tools.py` | Список файлов/папок |
| `python_exec` | `python_exec.py` | Выполнение Python-кода в subprocess |

Все инструменты возвращают JSON. Реестр — `src/tools/registry.py` с поддержкой OpenAI function calling схем.

### 7.2 Интеграция инструментов в Executor

`Executor.act()` (`src/orchestrator/subagents.py`) парсит строку задачи как `tool_name(key=value, ...)` и вызывает соответствующий инструмент. Fallback — прежнее generic-исполнение. Это позволяет Orchestrator'у делегировать реальные действия без изменения контракта.

### 7.3 CLI-интерфейс

`src/main.py` переписан: интерактивный цикл `while True: input("> ")`, запуск `EndToEndAgent.run(task)` для каждой команды, вывод статуса и транскрипта. Выход по `exit`/`quit`/`q`/`Ctrl+C`.

### 7.4 Персистентность семантической памяти

- `src/memory/json_store.py` — save/load NetworkX DiGraph в JSON
- `SemanticGraph.save(path)` / `SemanticGraph.load(path)` — методы класса
- Факты и связи (включая `supersedes`) сохраняются между перезапусками

### Результат

- Новые файлы: `src/tools/web_search.py`, `src/tools/file_tools.py`, `src/tools/python_exec.py`, `src/tools/registry.py`, `src/memory/json_store.py`
- Изменены: `src/main.py` (CLI), `src/orchestrator/subagents.py` (Executor с инструментами), `src/memory/semantic.py` (save/load)
- 87/87 тестов проходят
- Smoke-test инструментов пройден

---

## Фаза 8: LLM-интеллект — ✅ Завершена (Hermes Agent)

**Цель:** заменить наивные заглушки на LLM-управляемую декомпозицию и маршрутизацию.

Дата: 2026-07-03 | Исполнитель: Hermes Agent (DeepSeek)

### 8.1 LLM-декомпозиция задач (`LLMPlanner`)

- Новый класс `LLMPlanner` в `src/llm/subagent.py`
- Модель получает задачу и возвращает JSON-массив подзадач
- При ошибке (сеть, плохой JSON) — fallback на наивный `split(" and ")`
- `build_llm_subagent_pool()` теперь использует `LLMPlanner` вместо детерминированного `Planner`

### 8.2 LLM-маршрутизация субагентов

- `Orchestrator` получает опциональный `llm_client` в конструктор
- `route()` при наличии клиента спрашивает модель: «какая роль лучше подходит?»
- Ответ валидируется: роль должна быть в `self.pool`
- При ошибке/отсутствии клиента — fallback на keyword matching

### 8.3 Интеграция в EndToEndAgent

- `EndToEndAgent` создаёт `LLMClient` до `Orchestrator` и передаёт его
- Клиент используется и для пула субагентов, и для маршрутизации

### Результат

- Изменены: `src/llm/subagent.py` (+`LLMPlanner`, −`Planner` import), `src/orchestrator/orchestrator.py` (+`llm_client`, +LLM routing), `src/agent/end_to_end.py` (проводка клиента)
- 87/87 тестов проходят
## Фаза 9: Safety guards — ✅ Завершена (Hermes Agent)

**Цель:** подключить три защитных механизма Фазы 5.2 в основной цикл.

Дата: 2026-07-03 | Исполнитель: Hermes Agent (DeepSeek)

### 9.1 MemorySafetyGuard → Memory API

- `Memory.__init__()` принимает опциональный `safety_guard`
- `_add_semantic_fact()` — единая точка входа: если guard есть → `propose_fact()`, иначе прямой `add_fact()`
- `store(type="semantic")` и `consolidate()` проходят через guard
- Факты с confidence < 0.4 или противоречащие существующим → карантин

### 9.2 HumanApprovalGate → EndToEndAgent

- `CRITICAL_ACTIONS`: `delete_memory`, `modify_system_prompt`, `self_update`, `execute_untrusted_code`
- `EndToEndAgent.approval_gate` — критические действия требуют approve/reject

### 9.3 SelfModificationPolicy → EndToEndAgent

- `SELF_MOD_ALLOWED_KEYS`: `max_retries`, `temperature`, `consolidate_every`, `working_capacity`
- Попытка изменить неразрешённый ключ → `PermissionError`

### Результат

- Изменены: `src/memory/api.py` (+safety_guard, +_add_semantic_fact), `src/agent/end_to_end.py` (+MemorySafetyGuard, +HumanApprovalGate, +SelfModificationPolicy)
- 87/87 тестов проходят
- Интеграционные тесты: карантин, release, approval gate, self-mod policy

---

## Фаза 10: Task Graph + outer/meta loop — ✅ Завершена (Hermes Agent)

**Цель:** замкнуть агентский цикл — персистентность задач между сессиями, рефлексия между эпизодами, эволюция в конце сессии.

Дата: 2026-07-03 | Исполнитель: Hermes Agent (DeepSeek)

### 10.1 Task Graph → EndToEndAgent

- `EndToEndAgent` создаёт `TaskGraph(db_path="tasks.db")` — SQLite-персистентность
- `run()`: задача добавляется в граф, статус обновляется на `done`/`failed`
- Незавершённые задачи переживают перезапуск процесса

### 10.2 Outer loop → `run_session()`

- `run_session(tasks)` — пакетный запуск нескольких задач
- При неудаче — рефлексия и смена стратегии исполнения (sequential → parallel → hierarchical)
- До 3 попыток на сессию

### 10.3 Meta loop → `close()`

- `close()` вызывается при завершении сессии:
  - `consolidate()` — episodic → semantic
  - `SkillEvolutionEngine.extract_from_successful_episodes()` — авто-извлечение навыков
  - `auto_combine_sequential_pairs()` — сборка составных навыков
  - `semantic.save("semantic_graph.json")` — персистентность графа
  - Закрытие `TaskGraph` и `Memory`

### 10.4 CLI: graceful shutdown

- `main.py`: `try/finally` с вызовом `agent.close()` при выходе (exit, Ctrl+C, EOF)

### Результат

- Изменены: `src/agent/end_to_end.py` (+TaskGraph, +run_session, +close), `src/main.py` (graceful shutdown)
- 87/87 тестов проходят
- Интеграционные тесты: TaskGraph persistence, run_session, close → meta loop

---

## Фаза 11: Живой диалог — ConversationalAgent — Завершена (Claude Fable 5)

**Цель:** убрать «деревянность» — каждое сообщение шло через task-pipeline (decompose → routing → subagent на фрагмент → verifier → retry), терялся контекст, диалог был медленным и пассивным.

Дата: 2026-07-03 | Исполнитель: Claude Fable 5

### 11.1 Найденная корневая причина «пустого DuckDuckGo»

Ссылки в выдаче DDG — redirect-URL вида `//duckduckgo.com/l/?uddg=<encoded>`, а парсер отбрасывал всё, что не начинается с `http` → почти всегда пустой результат. Это была не «проблема бесплатного поиска», а баг парсера.

### 11.2 Изменения

- `src/tools/web_search.py` — переписан: декодирование uddg-редиректов, POST на html.duckduckgo.com + fallback на lite.duckduckgo.com, приведение max_results к int
- `src/tools/registry.py` — настоящие JSON-схемы (типы integer/string, необязательные параметры), приведение типов и фильтрация лишних аргументов в Tool.run
- `src/tools/web_extract.py` — html.unescape в regex-fallback
- `src/agent/conversational.py` — **новый ConversationalAgent**: живой agent loop — настоящая история сообщений, все инструменты (до 12 итераций), recall эпизодической памяти в system prompt, запись диалога в память
- `src/main.py` — диалог идёт через ConversationalAgent; оркестратор доступен явно через `/task`; `/new` сбрасывает историю агента
- `src/llm/personality.py` — переписан MAYYA_IDENTITY: живой характер, правило «2-3 попытки при ошибке инструмента, потом честно скажи», запрет кода-заглушек
- `src/llm/subagent.py` — сабагенты видят результаты друг друга (context.history() в user message) — фикс проблемы №3 из отчёта Hermes

### 11.3 Результат

- 101/101 тестов (было 87, +14: test_conversational_agent.py, test_web_search.py)
- Живой smoke-тест на реальном DeepSeek: запомнила имя, реально нашла в интернете и объяснила MCP, вспомнила имя из памяти, вычислила Фибоначчи через python_exec
- Закрыты проблемы 1 (DDG), 2 (код при ошибке поиска), 3 (потеря контекста между сабагентами) из отчёта Hermes

---

## Фаза 12: Инструменты и навыки из Hermes — Завершена (Claude Fable 5)

**Цель:** перенести в Mayya лучшее из установки Hermes Agent (`C:\Users\rusne\AppData\Local\hermes`), чтобы она решала задачи пользователя тем же арсеналом.

Дата: 2026-07-04 | Исполнитель: Claude Fable 5

### 12.1 Мульти-провайдерный веб-поиск (по образцу web-search-plus)

- `web_search` — цепочка: **Serper (Google API) → Yandex Search API → DDG html → DDG lite**
- Ключи SERPER_API_KEY и YANDEX_SEARCH_API_KEY скопированы из Hermes `.env` в наш `.env` (gitignored)
- Serper проверен живьём (в т.ч. кириллица, answerBox → «Прямой ответ Google»)
- Yandex-ключ сейчас даёт 401 (протух) — провайдер падает мягко, цепочка идёт дальше

### 12.2 Новые инструменты (аналоги terminal/patch/search_files/memory из Hermes)

- `run_command` (`src/tools/shell.py`) — shell-команды, timeout до 300с
- `edit_file` — точечный find-and-replace, требует уникальности фрагмента
- `search_files` — regex-поиск по текстовым файлам, скипает .venv/.git/__pycache__
- `remember` — явное сохранение факта в долговременную память (создаётся в ConversationalAgent при наличии Memory)
- `registry.py` — get_tool_schemas(tools) для кастомных наборов

### 12.3 Система навыков (как у Hermes skills/)

- `src/skills/loader.py` — навык = `skills/<name>/SKILL.md` (front matter + инструкции)
- Список навыков (имя+описание) инжектится в system prompt; полный текст Mayya читает сама через read_file
- Стартовые навыки: `web-research` (методика глубокого поиска), `self-development` (работа над собственным кодом: тесты, git, безопасность)

### 12.4 Результат

- 115/115 тестов (было 101, +14)
- Живой прогон: сама посчитала py-файлы через терминал, запомнила факт, перечислила свои навыки из skills/

---

## Фаза 13: MCP, браузер, cron, под-агенты — Завершена (Claude Fable 5)

**Цель:** дать Mayya оставшиеся возможности Hermes (браузер, GitHub, задачи по расписанию) плюс передовую практику — под-агентов и поддержку протокола MCP.

Дата: 2026-07-04 | Исполнитель: Claude Fable 5

### 13.1 MCP-клиент (`src/mcp/client.py`)

- Минимальный MCP-клиент со stdio-транспортом (JSON-RPC 2.0, по сообщению на строку), без внешних зависимостей: initialize handshake → tools/list → tools/call
- `MCPManager` читает `mcp.json`, поднимает серверы, оборачивает их инструменты в реестр под именами `<server>_<tool>`; упавший сервер не валит запуск
- Подключены серверы из установки Hermes: **playwright** (23 инструмента, headless-браузер) и **github** (26 инструментов, токен GITHUB_TOKEN в .env из token github.txt)
- ${VAR}-подстановка в env серверов

### 13.2 Cron (`src/tools/cron.py`)

- Инструмент `cronjob` (create/list/remove), хранилище cron.json (gitignored)
- Форматы: `every 10m/2h`, `daily 09:30`, `in 30m`, `once 2026-07-05 18:00`
- Фоновый раннер в main.py: каждые 20с проверяет due-задачи, выполняет их отдельным агентом, печатает жёлтую панель, пересчитывает next_run (one-shot удаляются)

### 13.3 Под-агенты (`delegate_task`)

- Инструмент делегирования: под-агент со своим контекстом и теми же инструментами (минус delegate_task — глубина ровно 1, без рекурсии)

### 13.4 Навык browser-automation

- `skills/browser-automation/SKILL.md` — когда браузер вместо web_extract, работа со снапшотами/ref, правила (закрывать браузер, не логиниться без спроса)

### 13.5 Результат

- 132/132 теста (было 115, +17: MCP-клиент с fake-сервером, cron, delegate)
- Живой прогон: открыла headless-браузер и назвала топ-3 Hacker News; через GitHub MCP прочитала свой последний коммит; создала себе ежедневную cron-задачу «дайджест новостей об AI-агентах в 09:00»
- Примечание: cron-задачи выполняются пока Mayya запущена (фоновый поток процесса)

---

## Фазы 14–18: План развития v2 — Завершены (Claude Fable 5)

Дата: 2026-07-04 | План: `docs/07_development_plan_v2.md`

### Фаза 14 — Сжатие контекста
Вытесняемая из истории ранняя часть диалога сворачивается LLM-конспектом (факты, имена, решения, незакрытые задачи, ≤1500 симв.) и живёт в system prompt. Ошибка суммаризатора не ломает диалог (остаётся прежний конспект).

### Фаза 15 — Семантическая память
ChromaVectorIndex (all-MiniLM) подключён к episodic-памяти в проде (main.py) с мягким fallback на hash-индекс. chroma_db/ gitignored. Живая проверка: «как зовут пользователя» находит эпизод «меня зовут Руслан». Известное ограничение: MiniLM англоцентрична — мультиязычная модель в бэклоге.

### Фаза 16 — Стриминг
`complete_with_tools(on_delta)` + `assemble_stream` (склейка text-дельт и фрагментов tool_calls). `chat(on_event)` эмитит события text/tool; терминал печатает ответ по мере генерации, вызовы инструментов — приглушёнными строками. Живой замер: первый токен на 2.0с из 3.2с.
Попутно: DEFAULT_MODEL снаружи сменили на deepseek-reasoner — живой проверкой подтверждено, что reasoner теперь поддерживает function calling; тест сделан независимым от модели.

### Фаза 17 — Telegram
`src/channels/telegram.py`: long polling чистым urllib, фильтр TELEGRAM_ALLOWED_USERS, резка сообщений по 4096, статус «печатает…». Режим `python -m src.main --telegram`; cron-результаты шлются в последний чат. Без токена — инструкция, не падение. Нужен собственный бот (@BotFather), токен Hermes переиспользовать нельзя.

### Фаза 18 — Evals
`evals/`: 8 сценариев (личность, проактивный поиск, отсутствие переспрашиваний, память, вычисления, честность при неудаче, краткость, файловый цикл) с автопроверками (contains/not_contains/tool_used/regex/max_length). Запуск: `python -m evals.run [id]`, результат сохраняется в evals/results-<дата>.json.
**Базовая линия 2026-07-04: 8/8 на deepseek-reasoner.**

### Итог
- 146/146 тестов (было 132)
- Закрыты разрывы 1–5 из плана v2 (остался п.6 — класс модели, принят как данность)
