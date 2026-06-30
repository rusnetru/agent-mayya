# Next Gen AI Agent — План разработки
> Дата: 2026-06-28 | Версия: 0.1 (черновик для обсуждения)

---

## КОНЦЕПЦИЯ: Что мы строим

**Next Gen Agent** — агент с постоянной памятью, иерархической командой субагентов, самоорганизующимися goal/loop циклами и способностью эволюционировать в процессе работы.

Ключевые отличия от существующих решений:
- Не stateless (помнит контекст между сессиями)
- Не monolithic (иерархия специализированных субагентов)
- Не static (топология команды и стратегия планирования адаптируются)
- Не tool-dependent (абстракция над протоколами MCP/A2A)

---

## ФАЗЫ РАЗРАБОТКИ

### ФАЗА 0: Фундамент (Недели 1–3)
**Цель:** Минимальная рабочая архитектура

#### 0.1 Выбор технологического стека — ЗАВЕРШЕНО
- [x] LLM backend: Anthropic Claude API (см. [docs/03_tech_stack.md](03_tech_stack.md))
- [x] Векторная БД: ChromaDB (локально) → Qdrant (production)
- [x] Граф памяти: NetworkX (прототип) → Neo4j (production)
- [x] Оркестрация: собственная реализация (raw SDK, без LangGraph)
- [x] Протоколы: MCP (инструменты) + заглушка A2A-интерфейса
- [x] Язык: Python 3.11+, сборка под Windows (PyInstaller)

#### 0.2 Базовый agent loop — ЗАВЕРШЕНО
```
[Perceive] → [Retrieve Memory] → [Plan] → [Act] → [Observe] → [Store Memory] → loop
```

Реализовано: `src/agent/loop.py` — минимальный ReAct-совместимый цикл с персистентной памятью.

#### 0.3 Слой памяти v1 — ЗАВЕРШЕНО
- [x] Working memory: context window management (`src/memory/working.py`, FIFO eviction)
- [x] Episodic store: SQLite-персистентность (`src/memory/episodic.py`)
- [x] Семантическая индексация: авто-консолидация episodic → semantic после N эпизодов (`src/memory/api.py`, `consolidate_every`)

**Фаза 0 завершена.** Memory API v1 (`src/memory/api.py`) реализует полный контракт: `store`, `retrieve`, `consolidate`, `skill_extract`. 10/10 тестов проходят. Следующий шаг — Фаза 1 (полноценная episodic engine с векторным поиском через ChromaDB) либо Фаза 2 (Orchestrator + субагенты).

---

### ФАЗА 1: Память (Недели 4–8) — ЗАВЕРШЕНО
**Цель:** Полноценная четырёхуровневая система памяти

#### 1.1 Episodic Memory Engine — ЗАВЕРШЕНО
- [x] Захват событий с метаданными: timestamp, context, who, where, why (`src/memory/episodic.py`)
- [x] Single-shot learning без gradient updates — эпизод доступен для retrieval сразу после store
- [x] Retrieval: hybrid векторно-граф поиск (`src/memory/vector_index.py` — хешированные bag-of-words эмбеддинги + keyword match; production-замена — ChromaDB embedding function без изменения интерфейса)

#### 1.2 Memory Consolidation Pipeline — ЗАВЕРШЕНО
- [x] Периодическое сжатие: episodic → semantic (`Memory.consolidate()`, авто-триггер по `consolidate_every`)
- [x] Вытеснение старых / малорелевантных воспоминаний (`EpisodicMemory.forget_before()` / `Memory.forget()`)
- [x] Версионирование памяти (SSGM-inspired): `SemanticGraph.update_fact()` создаёт новую версию через `supersedes`-связь, не удаляя старый факт; `history()` восстанавливает цепочку версий

#### 1.3 Procedural Memory Store — ЗАВЕРШЕНО
- [x] Хранение успешных паттернов действий как Skills (`src/memory/skills.py`)
- [x] Автоматическое извлечение Skills из эпизодов (`Memory.skill_extract()`)
- [x] Самосовершенствование Skills (Hermes-inspired): `SkillStore.combine()` собирает составной skill из двух валидированных; ранжирование по `success_rate`

#### 1.4 Memory API — ЗАВЕРШЕНО
```python
memory.store(event, type="episodic", context={...}, who=..., where=..., why=...)
memory.retrieve(query, top_k=5, types=["episodic", "semantic"])
memory.consolidate()  # episodic → semantic
memory.skill_extract(episode_id)  # авто-извлечение навыка
memory.forget(cutoff_timestamp)  # вытеснение старых эпизодов
```

**Фаза 1 завершена.** 17/17 тестов проходят. Следующий шаг — Фаза 2 (Orchestrator + иерархия субагентов).

---

### ФАЗА 2: Иерархия субагентов (Недели 9–14) — ЗАВЕРШЕНО
**Цель:** Оркестратор + пул специализированных субагентов

#### 2.1 Orchestrator Agent — ЗАВЕРШЕНО
- [x] Декомпозиция задачи на подзадачи (`Orchestrator.decompose()` → `Planner.decompose()`)
- [x] Выбор и инициализация нужных субагентов (`Orchestrator.route()` — keyword-based routing)
- [x] Сборка и верификация результатов (`Verifier` + `MemoryCurator` запускаются после исполнения, итог собирается в `transcript`)
- [x] Поддержка паттернов: sequential / parallel / hierarchical (`Orchestrator.run(pattern=...)`)

#### 2.2 Базовые субагенты (встроенные) — ЗАВЕРШЕНО
| Агент | Роль | Файл |
|-------|------|------|
| **Researcher** | Поиск и синтез информации | `src/orchestrator/subagents.py` |
| **Executor** | Выполнение кода и инструментов | `src/orchestrator/subagents.py` |
| **Verifier** | Проверка результатов | `src/orchestrator/subagents.py` |
| **Planner** | Декомпозиция и планирование | `src/orchestrator/subagents.py` |
| **Memory Curator** | Управление памятью, консолидация (использует Memory API из Фазы 1) | `src/orchestrator/subagents.py` |

#### 2.3 Динамическая топология — ЗАВЕРШЕНО
- [x] Топология команды не фиксирована — `Orchestrator.pool` это реестр ролей
- [x] Orchestrator может создавать/убирать субагентов под задачу: `register()` / `unregister()`
- [x] Маршрутизация подзадач к ролям по ключевым словам (`route()`), легко расширяемая под новые типы субагентов

#### 2.4 Subagent Communication Layer — ЗАВЕРШЕНО
- [x] Протокол передачи контекста между субагентами: `SharedContext` (`src/orchestrator/communication.py`)
- [x] Shared working memory для команды: `SharedContext.data` (key/value) + `SharedContext.transcript` (append-only лог сообщений)
- [x] Структура достаточно нейтральна для использования как A2A-совместимый payload во внешней интеграции (задел, полноценный A2A-протокол — за рамками Фазы 2)

**Фаза 2 завершена.** 28/28 тестов проходят (11 новых для orchestrator/subagents/communication).

---

### ФАЗА 3: Goal/Loop архитектура (Недели 15–20) — ЗАВЕРШЕНО
**Цель:** Автоматическое планирование и самокоррекция

#### 3.1 Goal Management System — ЗАВЕРШЕНО
```
Goal Stack:
  [Long-term goal]
    [Mid-term objective]
      [Current task]
        [Immediate action]
```

- [x] Иерархия целей с разными горизонтами (`src/goals/goal_stack.py`, `Horizon = long_term/mid_term/task/action`)
- [x] Автоматическая декомпозиция goal → subgoals (`GoalStack.decompose()`, на один горизонт глубже)
- [x] Пересмотр целей при изменении контекста (`GoalStack.revise()`, `active_leaves()` — что делать прямо сейчас)

#### 3.2 Planning Engine — ЗАВЕРШЕНО
- [x] Базовый: ReAct loop с self-critique (Reflexion-style) — `react_with_self_critique()` в `src/planning/engine.py`
- [x] Расширенный: упрощённый MCTS для выбора действий (LATS-inspired) — `mcts_select_action()` (UCB1 + симуляции)
- [x] Мета: выбор стратегии планирования по накопленной статистике успеха (TodoEvolve-inspired) — `StrategyRegistry`

#### 3.3 Task-Decoupled Execution — ЗАВЕРШЕНО
- [x] Отделено «что делать» (`TaskGraph`) от «как делать сейчас» (caller передаёт `execute()`)
- [x] Persistent task graph: незавершённые задачи сохраняются между сессиями (SQLite, `src/tasks/task_graph.py`)
- [x] DAG-based workflow: зависимости между задачами, `ready_tasks()` отдаёт независимые ветки для параллельного запуска

#### 3.4 Self-Correction Loops — ЗАВЕРШЕНО
```
Inner loop:  act → verify → retry  (per action)
Outer loop:  episode → reflect → update strategy  (per task)
Meta loop:   project → consolidate → evolve capabilities  (long-term)
```
Реализовано как универсальные драйверы над callable-аргументами в `src/loops/self_correction.py` (`inner_loop`, `outer_loop`, `meta_loop`) — не привязаны к конкретной реализации Orchestrator/Planning Engine, оборачивают любые act/verify/reflect/consolidate/evolve функции.

**Фаза 3 завершена.** 49/49 тестов проходят (21 новый: goal stack, planning engine, task graph, self-correction loops).

---

### ФАЗА 4: Эволюция и самосовершенствование (Недели 21–28)
**Цель:** Агент улучшает себя в процессе работы

#### 4.1 Skill Evolution Engine
- Автоматическое создание Skills из успешных эпизодов
- Оценка и рейтинг Skills по частоте использования и успешности
- Комбинирование Skills в более сложные

#### 4.2 Strategy Adaptation
- Агент отслеживает, какие стратегии планирования работают для каких классов задач
- Адаптирует подход на основе накопленного опыта
- Не перезаписывает себя (в отличие от Hyperagents) — только конфигурацию

#### 4.3 Team Composition Learning
- Система учится, какие комбинации субагентов эффективны для каких задач
- История успехов/неудач команд сохраняется в semantic memory

---

### ФАЗА 5: Производственная готовность (Недели 29–36)
**Цель:** Надёжность, наблюдаемость, масштабируемость

#### 5.1 Observability
- Полный трейсинг всех действий агента
- Визуализация memory state и goal stack
- Dashboard для мониторинга команды субагентов

#### 5.2 Safety & Governance
- SSGM-inspired memory safety: защита от drift и отравления памяти
- Human-in-the-loop точки для критических решений
- Ограничения на самомодификацию

#### 5.3 Scalability
- Асинхронное исполнение субагентов
- Horizontal scaling оркестратора
- Distributed memory (переход с SQLite → cloud vector DB)

---

## АРХИТЕКТУРНАЯ ДИАГРАММА

```
┌─────────────────────────────────────────────────────┐
│                  USER / EXTERNAL SYSTEM              │
└────────────────────────┬────────────────────────────┘
                         │  A2A / REST / CLI
┌────────────────────────▼────────────────────────────┐
│              ORCHESTRATOR AGENT                      │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │
│  │ Goal Manager │  │Planning Eng. │  │ Task DAG  │  │
│  └──────────────┘  └──────────────┘  └───────────┘  │
└────────┬──────────────────────────────┬─────────────┘
         │ spawn / delegate             │ read/write
┌────────▼──────────────────┐  ┌────────▼─────────────┐
│     SUBAGENT POOL         │  │    MEMORY SYSTEM      │
│  ┌──────────┐ ┌────────┐  │  │  ┌─────────────────┐ │
│  │Researcher│ │Exectr. │  │  │  │ Working Memory  │ │
│  └──────────┘ └────────┘  │  │  ├─────────────────┤ │
│  ┌──────────┐ ┌────────┐  │  │  │ Episodic Store  │ │
│  │Verifier  │ │Planner │  │  │  ├─────────────────┤ │
│  └──────────┘ └────────┘  │  │  │ Semantic Graph  │ │
│  ┌──────────┐             │  │  ├─────────────────┤ │
│  │Mem.Curat.│             │  │  │ Skill Store     │ │
│  └──────────┘             │  │  └─────────────────┘ │
└────────┬──────────────────┘  └──────────────────────┘
         │ MCP
┌────────▼──────────────────────────────────────────┐
│              TOOLS / EXTERNAL APIs                 │
│  [Web Search] [Code Exec] [Files] [Databases] ...  │
└───────────────────────────────────────────────────┘
```

---

## ПРИОРИТЕТЫ ИССЛЕДОВАНИЙ ДЛЯ КОМАНДЫ

### Нужно изучить детально (до начала разработки)
1. **CoALA Framework** (arXiv:2309.02427) — формальная основа для типов памяти
2. **AgentOrchestra** (arXiv:2506.12508) — детальная архитектура оркестрации
3. **TodoEvolve** (arXiv:2602.07839) — мета-планирование
4. **MetaGen** (arXiv:2601.19290) — эволюция топологий
5. **SSGM** (arXiv:2603.11768) — безопасность памяти
6. **A2A Protocol Spec** (a2a-protocol.org) — стандарт коммуникации

### Эксперименты для валидации гипотез
- [ ] Сравнить vector-only vs. vector+graph retrieval для episodic memory
- [ ] Измерить влияние memory consolidation на качество долгосрочных задач
- [ ] Протестировать иерархическую vs. flat архитектуру субагентов
- [ ] Оценить MCTS vs. greedy ReAct для планирования

---

## ОТКРЫТЫЕ ВОПРОСЫ

1. **Catastrophic forgetting** — как обновлять семантическую память без потери важного?
2. **Memory poisoning** — как защититься от ошибочных воспоминаний, влияющих на поведение?
3. **Agent identity** — как агент сохраняет консистентную «личность» при эволюции?
4. **Coordination overhead** — при каком размере команды субагентов коммуникация начинает перевешивать пользу?
5. **Evaluation metrics** — как измерять «качество» агента на длинных горизонтах?

---

## СЛЕДУЮЩИЕ ШАГИ (ближайшие 2 недели)

- [ ] Прочитать и законспектировать 6 приоритетных статей
- [ ] Определить технологический стек (обсуждение)
- [ ] Написать спецификацию Memory API
- [ ] Создать репозиторий и базовую структуру проекта
- [ ] Реализовать proof-of-concept: агент с персистентной episodic memory
