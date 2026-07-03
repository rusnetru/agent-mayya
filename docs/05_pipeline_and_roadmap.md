# Next Gen Agent — Текущий пайплайн и план следующей разработки

> Дата снимка: 2026-06-30 | Тестов: 87/87 | Репозиторий: https://github.com/rusnetru/next-gen-agent

---

## 1. Текущий пайплайн (что реально работает сейчас)

### 1.1 Точка входа — `run.bat` / `python -m src.main`

```
run.bat
  └─ проверяет/создаёт .venv
  └─ pip install -r requirements.txt (если первый раз)
  └─ python -m src.main
       └─ load_dotenv() → читает DEEPSEEK_API_KEY из .env
       └─ EndToEndAgent(use_llm=True если есть ключ)
       └─ agent.run(task)
```

### 1.2 Цикл одного запуска (`src/agent/end_to_end.py`)

```
EndToEndAgent.run(task, task_class)
│
├─ GoalStack.push(task)              — регистрируем задачу как цель (horizon=task)
│
├─ StrategyAdapter.select(task_class) — выбираем паттерн исполнения
│   └─ StrategyRegistry              (sequential / parallel / hierarchical)
│      по истории успехов для этого класса задач
│
├─ inner_loop(max_retries=2)         — self-correction: retry если Verifier вернул FAIL
│   └─ Orchestrator.run(task, pattern)
│       ├─ Planner.decompose(task)       — нарезаем на подзадачи
│       ├─ route(subtask) → role         — keyword → роль субагента
│       ├─ [Researcher / Executor].act() → LLM-вызов DeepSeek (deepseek-chat)
│       ├─ Verifier.act()                → LLM оценивает результат (PASS/FAIL)
│       └─ MemoryCurator.act()           → пишет в episodic memory + consolidate()
│
├─ StrategyAdapter.observe(success)  — обновляем статистику стратегий
├─ GoalStack.revise(active=False)    — деактивируем выполненную цель
└─ Tracer.record(...)                — фиксируем события для observability
```

### 1.3 Память (4 уровня, `src/memory/`)

| Уровень | Модуль | Хранение | Статус |
|---|---|---|---|
| Working Memory | `working.py` | In-memory (deque, FIFO eviction) | Работает |
| Episodic Memory | `episodic.py` | SQLite (`memory.db`) + VectorIndex (in-memory, пересобирается из SQLite) | Работает, персистентно |
| Semantic Memory | `semantic.py` | NetworkX DiGraph (in-memory, не персистентен) | Работает, пересобирается |
| Procedural Memory | `skills.py` | In-memory SkillStore | Работает |
| Memory API | `api.py` | Фасад над всеми уровнями | Работает |

Векторный поиск: `vector_index.py` — хешированные bag-of-words эмбеддинги, офлайн, детерминированно. Планируемая замена — ChromaDB/Qdrant (уже в `requirements.txt`, в код не подключён).

### 1.4 LLM-слой (`src/llm/`)

- **Провайдер:** DeepSeek (`api.deepseek.com`), модель `deepseek-chat`
- **SDK:** `openai` (DeepSeek OpenAI-совместим, только `base_url` другой)
- **Ключ:** `DEEPSEEK_API_KEY` в `.env` (исключён `.gitignore`, в git не попадает)
- **Fallback:** без `.env` агент работает на детерминированных заглушках субагентов (без сетевых вызовов)
- **Субагенты через LLM:** Researcher, Executor, Verifier — через `LLMSubagent`/`LLMVerifier`
- **Субагенты детерминированные:** Planner (декомпозиция), MemoryCurator (работа с памятью)

### 1.5 Оркестрация (`src/orchestrator/`)

- `Orchestrator` — реестр ролей (`pool`), маршрутизация по ключевым словам, 3 паттерна исполнения
- `SharedContext` — shared working memory команды за один прогон (data + transcript)
- Динамическая топология: `register()` / `unregister()` в рантайме

### 1.6 Модули, реализованные но не интегрированные в основной цикл

| Модуль | Файл | Статус интеграции |
|---|---|---|
| Goal Stack | `src/goals/goal_stack.py` | Интегрирован в EndToEndAgent |
| Planning Engine (ReAct+critique, MCTS, StrategyRegistry) | `src/planning/engine.py` | StrategyRegistry используется; ReAct/MCTS — не задействованы в main-цикле |
| Task Graph (DAG, SQLite) | `src/tasks/task_graph.py` | ✅ Интегрирован (Фаза 10): persist в EndToEndAgent |
| Self-Correction (inner/outer/meta loop) | `src/loops/self_correction.py` | ✅ Интегрированы (Фаза 10): inner+outer+meta в EndToEndAgent |
| Skill Evolution Engine | `src/evolution/skill_evolution.py` | ✅ Интегрирован (Фаза 10): meta loop → close() |
| Team Composition Learning | `src/evolution/team_composition.py` | ✅ Интегрирован (Фаза 12): record team + success after each run() |
| LLM Planner (декомпозиция) | `src/llm/subagent.py` | ✅ LLMPlanner с fallback (Фаза 8) |
| LLM Routing (маршрутизация) | `src/orchestrator/orchestrator.py` | ✅ LLM-route с fallback на keywords (Фаза 8) |
| Observability (Tracer, dashboard) | `src/observability/` | Tracer используется в EndToEndAgent; dashboard — вызывается вручную |
| Safety (MemorySafetyGuard, HumanApprovalGate, SelfModificationPolicy) | `src/safety/` | ✅ Интегрированы (Фаза 9): guard в Memory, gate+policy в EndToEndAgent |
| Async execution | `src/scalability/async_execution.py` | Реализован, в main-цикл не встроен |
| CLI Interface | `src/main.py` | ✅ Реализован (Фаза 7): интерактивный цикл `while True: input()` |
| Self-update (git pull) | `src/update/self_update.py` | Реализован, вызывается вручную через `update.ps1` |
| Semantic Memory (JSON persistence) | `src/memory/semantic.py` + `json_store.py` | ✅ Реализовано (Фаза 7): save/load через JSON |
| Tools | `src/tools/` | ✅ Реализованы (Фаза 7): web_search, file R/W, list_dir, python_exec + registry |

---

## 2. Следующий план разработки

Приоритеты обновлены 2026-07-03 после Фазы 7.

### Выполнено (Фаза 7-10, Hermes Agent)
- ✅ Инструменты: web_search, file R/W, list_dir, python_exec + registry
- ✅ CLI-интерфейс: интерактивный цикл в `main.py`
- ✅ Semantic memory JSON-персистентность (save/load)
- ✅ LLM-декомпозиция задач: `LLMPlanner` с fallback на `split(" and ")`
- ✅ LLM-маршрутизация субагентов: `Orchestrator.route()` с fallback на keywords
- ✅ Safety guards: MemorySafetyGuard → Memory, HumanApprovalGate + SelfModificationPolicy → EndToEndAgent
- ✅ ChromaDB: `ChromaVectorIndex` — drop-in замена `VectorIndex`, реальные embeddings
- ✅ Team Composition Learning: запись состава команды после каждого run()

---

### Приоритет 1: Интерфейсы

#### ✅ ChromaDB — реальные embeddings (Фаза 11)
`ChromaVectorIndex` — drop-in замена `VectorIndex`, семантический поиск через `all-MiniLM-L6-v2`.

#### 1.1 Telegram-бот
**Проблема:** только CLI — нет удалённого доступа.  
**Решение:** лёгкий Telegram-бот через python-telegram-bot, запускающий EndToEndAgent в каждом сообщении.  
**Объём:** ~100 строк

---

### Приоритет 4: ChromaDB — реальные embeddings

**Проблема:** текущий `VectorIndex` (хешированные bag-of-words) не понимает семантику — "купить машину" и "приобрести автомобиль" не найдутся по запросу "транспорт".  
**Решение:** реализовать `ChromaVectorIndex` класс, реализующий интерфейс `VectorIndex`, переключить `EpisodicMemory` на него через конфигурацию. ChromaDB уже в `requirements.txt`.  
**Файл:** `src/memory/vector_index.py`, `src/memory/episodic.py`  
**Объём:** ~40 строк

---

## 3. Что НЕ делаем в ближайшее время

| Пункт | Почему откладываем |
|---|---|
| Horizontal scaling оркестратора | Нужен реальный деплой (несколько нод) — пока нет production-окружения |
| Qdrant / Neo4j | Production-инфраструктура, нужна только при реальной нагрузке |
| Полноценный A2A-протокол | Нет внешних агентов для интеграции прямо сейчас |
| Полноценный MCTS | Toy-реализация достаточна; улучшать когда появятся реальные задачи для бенчмарка |

---

## 4. Текущая структура файлов

```
next-gen-agent/
├── run.bat                        ← одной кнопкой запустить агента
├── install.ps1                    ← первичная установка
├── update.ps1                     ← git pull + переустановка зависимостей
├── build.ps1                      ← (опц.) сборка Windows .exe
├── .env                           ← DEEPSEEK_API_KEY (не в git)
├── requirements.txt               ← anthropic, openai, chromadb, networkx, ...
├── src/
│   ├── main.py                    ← точка входа
│   ├── agent/
│   │   ├── loop.py                ← минимальный Phase 0 loop (legacy)
│   │   └── end_to_end.py          ← ← ОСНОВНОЙ ЦИКЛ (Phase 6)
│   ├── llm/
│   │   ├── client.py              ← DeepSeek API client
│   │   └── subagent.py            ← LLMSubagent, LLMVerifier, build_llm_subagent_pool()
│   ├── memory/
│   │   ├── api.py                 ← Memory (фасад: store/retrieve/consolidate/skill_extract)
│   │   ├── episodic.py            ← SQLite + VectorIndex hybrid retrieval
│   │   ├── semantic.py            ← NetworkX graph (версионирование фактов)
│   │   ├── skills.py              ← SkillStore (extract, combine, rank)
│   │   ├── vector_index.py        ← хешированные bag-of-words эмбеддинги
│   │   └── working.py             ← bounded deque (context window)
│   ├── orchestrator/
│   │   ├── orchestrator.py        ← Orchestrator (decompose, route, run sequential/parallel/hierarchical)
│   │   ├── subagents.py           ← Researcher, Executor, Verifier, Planner, MemoryCurator (стабы)
│   │   └── communication.py       ← SharedContext (data + transcript)
│   ├── goals/
│   │   └── goal_stack.py          ← GoalStack (4 горизонта, decompose, revise, active_leaves)
│   ├── planning/
│   │   └── engine.py              ← ReAct+critique, MCTS, StrategyRegistry
│   ├── tasks/
│   │   └── task_graph.py          ← TaskGraph DAG (SQLite, depends_on, ready_tasks)
│   ├── loops/
│   │   └── self_correction.py     ← inner_loop, outer_loop, meta_loop
│   ├── evolution/
│   │   ├── skill_evolution.py     ← SkillEvolutionEngine (extract, rank, auto_combine)
│   │   ├── strategy_adaptation.py ← StrategyAdapter (select/observe по истории)
│   │   └── team_composition.py    ← TeamCompositionLearner (semantic memory)
│   ├── observability/
│   │   ├── tracer.py              ← Tracer (structured events, export JSON)
│   │   └── dashboard.py           ← snapshot() (memory + goals state)
│   ├── safety/
│   │   ├── memory_guard.py        ← MemorySafetyGuard (карантин фактов)
│   │   └── governance.py          ← HumanApprovalGate, SelfModificationPolicy
│   ├── scalability/
│   │   └── async_execution.py     ← run_async() (asyncio parallel subagents)
│   ├── update/
│   │   └── self_update.py         ← git pull self-update API
│   ├── tools/
│   │   ├── __init__.py             ← package marker
│   │   ├── registry.py             ← Tool + REGISTRY + OpenAI function schemas
│   │   ├── web_search.py           ← DuckDuckGo HTML search (no API key)
│   │   ├── file_tools.py           ← read_file, write_file, list_dir
│   │   └── python_exec.py          ← subprocess Python execution
│   └── memory/
│       └── json_store.py           ← NetworkX ↔ JSON save/load
├── tests/                         ← 87 тестов (pytest)
└── docs/
    ├── 00_progress_log.md         ← журнал по фазам с коммитами
    ├── 01_research_landscape.md   ← обзор существующих решений
    ├── 02_development_plan.md     ← план фаз 0-6
    ├── 03_tech_stack.md           ← зафиксированный стек
    ├── 04_deployment.md           ← установка, обновление, run.bat
    └── 05_pipeline_and_roadmap.md ← этот файл
```
