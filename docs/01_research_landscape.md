# Next Gen AI Agent — Исследование архитектур
> Дата: 2026-06-28 | Статус: черновик v0.1

---

## 1. ОРГАНИЗАЦИЯ ПАМЯТИ

### 1.1 Базовая таксономия (CoALA Framework, Princeton)
Четыре типа памяти, заимствованные из когнитивной науки Эндела Тулвинга (1972) и адаптированные для LLM:

| Тип | Описание | Хранение | Аналог у человека |
|-----|----------|----------|-------------------|
| **Working (In-context)** | Текущий контекст разговора/задачи | Context window | Рабочая память |
| **Episodic** | Конкретные события прошлого с контекстом (кто/где/когда) | Vector DB / файлы | Автобиографическая память |
| **Semantic** | Обобщённые факты, абстракции | Knowledge graph / DB | Энциклопедическая память |
| **Procedural** | Навыки, инструкции, код | Промпты / code store | Навыки и привычки |

### 1.2 Ключевые прорывы 2025–2026

**Episodic Memory is the Missing Piece (arXiv:2502.06975, Feb 2026)**
Центральный тезис: именно эпизодическая рефлексия и консолидация — конвертация прошлых событий в компактные переиспользуемые представления — является ключевым механизмом для долгосрочного рассуждения.

Пять обязательных свойств эпизодической памяти агента:
1. **Long-term storage** — персистентность за пределами сессии
2. **Explicit reasoning** — способность рефлексировать над содержимым памяти
3. **Single-shot learning** — захват информации из единственного взаимодействия без градиентного обновления
4. **Instance-specific memories** — детали уникального события (не обобщение)
5. **Contextual binding** — кто, когда, где, почему привязано к содержимому

**Memory-R1**
Формулирует операции с памятью как действия, оптимизируемые обученной политикой. Агент сам решает: читать / записывать / объединять / удалять воспоминания.

**MemAct**
Агент встраивает операции с памятью прямо в chain-of-thought, не разделяя «думаю» и «запоминаю».

**SSGM Framework (arXiv:2603.11768)**
Stability and Safety Governed Memory — управление эволюцией памяти с гарантиями стабильности и безопасности. Решает проблему drift памяти со временем.

### 1.3 Архитектурные паттерны хранения

```
Уровень 1: Vector similarity search  →  семантически похожие факты
Уровень 2: Graph-based retrieval     →  факты через сущности и связи
Уровень 3: Episodic log              →  хронология событий с контекстом
Уровень 4: Procedural store          →  навыки/код/шаблоны действий
```

**Тренд:** память движется от pure vector search → гибридные векторно-граф системы с явной эпизодической историей.

**Консолидация:** ключевой механизм — периодическое сжатие эпизодической → семантическую память (как сон у человека).

---

## 2. АРХИТЕКТУРА СУБАГЕНТОВ

### 2.1 Паттерны оркестрации (сравнительное исследование, arXiv:2603.22651)

| Паттерн | Описание | Точность | Стоимость |
|---------|----------|----------|-----------|
| **Sequential pipeline** | A → B → C | базовая | низкая |
| **Parallel fan-out** | A → [B, C, D] → merge | высокая | средняя |
| **Hierarchical supervisor-worker** | orchestrator → [subagents] | 97.7% от max | 60.9% от max |
| **Reflexive self-correcting loop** | агент проверяет себя | максимальная | высокая |

**Вывод:** иерархическая архитектура даёт наилучший баланс точность/стоимость.

### 2.2 AgentOrchestra (arXiv:2506.12508, Jun 2025)
State-of-the-art на SimpleQA: **95.3% accuracy**.

Структура:
```
Planning Agent (orchestrator)
├── Browser Use Agent      — поиск и извлечение информации
├── Deep Researcher Agent  — верификация и глубокий анализ
└── [динамически создаваемые специализированные агенты]
```

### 2.3 Топологии взаимодействия

**TopoDIM (arXiv:2601.10120)** — One-shot генерация разнообразных топологий взаимодействия для мульти-агентных систем. Позволяет автоматически подбирать оптимальную топологию под задачу.

**MetaGen (arXiv:2601.19290)** — Self-Evolving Roles and Topologies: роли и топология команды агентов эволюционируют в процессе решения задачи.

### 2.4 HALO Framework (arXiv:2505.13516)
Hierarchical Autonomous Logic-Oriented Orchestration — формальная модель иерархической оркестрации с чёткими уровнями ответственности.

---

## 3. GOAL/LOOP ЦИКЛЫ И АВТОМАТИЧЕСКОЕ ПЛАНИРОВАНИЕ

### 3.1 Эволюция от ReAct к современным подходам

```
ReAct (2022)         →  Think → Act → Observe (базовый loop)
Reflexion (2023)     →  + self-critique после каждого эпизода
LATS (2023)          →  ReAct + MCTS дерево для выбора действий
AgentQ (2024)        →  MCTS + RL обучение политики планирования
TodoEvolve (2026)    →  автоматическое проектирование структуры планировщика
```

**AgentQ (OpenReview)** — Advanced Reasoning and Learning: объединяет MCTS для поиска по дереву решений с RL-оптимизацией политики. Агент сам учится планировать, используя верифицируемые траектории.

### 3.2 Task-Decoupled Planning (arXiv:2601.07577)
**Beyond Entangled Planning** — ключевая идея: разделить планирование задач от исполнения, чтобы long-horizon агенты не путали «что сделать» с «как сделать прямо сейчас».

### 3.3 TodoEvolve (arXiv:2602.07839)
**Learning to Architect Agent Planning Systems** — мета-планировщик, который обучается синтезировать саму структуру планирования под конкретный класс задач. Движение от policy optimization к автономному синтезу планировочных структур.

### 3.4 Hermes Agent Framework
Операционализирует модель perception → memory → action с механизмом самоэволюции:
- Замкнутый цикл обучения
- Агент автономно создаёт переиспользуемые Skills
- Skills самосовершенствуются при последующих применениях

### 3.5 DAG-based Workflow Orchestration
Современные системы (FlowSearch, JoyAgent, Co-Sight) используют DAG (Directed Acyclic Graph) для представления workflow вместо линейных цепочек. Это позволяет:
- Параллельное исполнение независимых подзадач
- Явное отслеживание зависимостей
- Динамическое добавление узлов

---

## 4. КОМАНДНОЕ ВЗАИМОДЕЙСТВИЕ АГЕНТОВ

### 4.1 Протоколы межагентной коммуникации

**Стек протоколов 2025–2026:**
```
MCP  (Anthropic, 2024)  →  Agent ↔ Tools/Resources
A2A  (Google, Apr 2025) →  Agent ↔ Agent
ACP                     →  Agent Communication Protocol
ANP                     →  Agent Network Protocol
```

**A2A Protocol:**
- Объявлен Google в апреле 2025, 50+ корпоративных партнёров
- Передан Linux Foundation в июне 2025
- v1.0 в начале 2026, 150+ организаций в production (AWS, Microsoft, Salesforce, SAP, IBM)
- Технический стек: HTTP/1.1+2, JSON-RPC 2.0, SSE, опционально gRPC

**Ключевое разделение:**
- MCP = агент ↔ инструменты (вертикальное подключение)
- A2A = агент ↔ агент (горизонтальное взаимодействие)

### 4.2 Паттерны командного решения задач

**Beyond Self-Talk (arXiv:2502.14321)** — исчерпывающий survey коммуникации в мульти-агентных системах:
- Discussion-style координация
- Debate-style протоколы (агенты спорят и достигают консенсуса)
- Role-based организация (planner / executor / verifier)

**Maestro (arXiv:2511.06134)** — Learning to Collaborate via Conditional Listwise Policy Optimization. Агенты обучаются оптимальным стратегиям коллаборации.

**Metacognitive Policy Optimization (arXiv:2603.07972)** — адаптивная коллаборация с людьми: агент-команда учится знать когда и как просить человека о помощи.

### 4.3 Динамические топологии команд

**MetaGen** — роли и топология команды не фиксированы, а эволюционируют в процессе решения задачи.

**TopoDIM** — one-shot генерация топологии: система сама выбирает нужную структуру команды под конкретную задачу.

---

## 5. ПРОРЫВЫ ЗА ПРЕДЕЛАМИ ОСНОВНЫХ ЗОН ИНТЕРЕСОВ ⚡

### 5.1 Self-Evolving Agents — Новая парадигма
**Survey (arXiv:2508.07407)** — «A New Paradigm Bridging Foundation Models and Lifelong Agentic Systems»

Агент автономно модифицирует свои внутренние компоненты (промпты, память, инструменты) на основе обратной связи из среды. Четыре компонента цикла самоэволюции:
1. System Inputs (цели и задачи)
2. Agent System (foundation model + промпты + модули памяти)
3. Environment (инструменты, внешний мир)
4. Feedback → обратно в System

### 5.2 Hyperagents / Gödel Machines
Самореференциальные агенты, сливающие task agent и meta-agent в единую программу. Агент авторизован перезаписывать собственный исходный код, если изменения ведут к доказуемо лучшей производительности. Формальная основа — машина Гёделя.

### 5.3 World Models для агентов
**Aligning Agentic World Models (arXiv:2601.13247)** — агент строит внутреннюю модель мира (world model) и использует её для предсказания последствий действий перед исполнением. Позволяет существенно снизить количество реальных взаимодействий со средой.

### 5.4 Beyond Transformers — новые архитектурные основания (2026)
По данным Adaline Labs, семь прорывов изменяют production в 2026:
- Mamba/SSM архитектуры для длинного контекста без квадратичной сложности внимания
- Mixture-of-Experts (MoE) для динамической активации параметров
- Test-time compute scaling — вычисления во время инференса (o1/o3-style)

### 5.5 Пространственный интеллект
Переход от language-only AI к spatially-aware intelligence, понимающей физическую реальность. Критично для агентов в робототехнике и embodied AI.

### 5.6 Катастрофическое незабывание
Continual learning без catastrophic forgetting — агенты обновляются непрерывно, не теряя предыдущих знаний. Одна из главных нерешённых проблем для долгоживущих агентов.

---

## 6. КЛЮЧЕВЫЕ ИСТОЧНИКИ

- [State of AI Agent Memory 2026](https://mem0.ai/blog/state-of-ai-agent-memory-2026)
- [AgentOrchestra: Hierarchical Multi-Agent Framework](https://arxiv.org/html/2506.12508v1)
- [Survey of Agent Interoperability Protocols: MCP, ACP, A2A, ANP](https://arxiv.org/html/2505.02279v1)
- [Beyond Self-Talk: Communication in Multi-Agent Systems](https://arxiv.org/pdf/2502.14321)
- [Self-Evolving AI Agents Survey](https://arxiv.org/abs/2508.07407)
- [MetaGen: Self-Evolving Roles and Topologies](https://arxiv.org/pdf/2601.19290)
- [TodoEvolve: Learning to Architect Planning Systems](https://arxiv.org/pdf/2602.07839)
- [Governing Evolving Memory (SSGM)](https://arxiv.org/html/2603.11768v1)
- [A2A Protocol](https://a2a-protocol.org/latest/)
- [AI Agent Breakthroughs 2026 — Adaline Labs](https://labs.adaline.ai/p/the-ai-research-landscape-in-2026)
- [Awesome AI Agent Papers 2026](https://github.com/VoltAgent/awesome-ai-agent-papers)
