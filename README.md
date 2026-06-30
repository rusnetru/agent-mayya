# Next Gen Agent

ИИ-агент нового поколения: постоянная память, иерархическая команда субагентов,
самоорганизующиеся goal/loop циклы и способность эволюционировать в процессе работы.

## Ключевые архитектурные принципы

- **Не stateless** — агент помнит контекст между сессиями (episodic + semantic memory).
- **Не monolithic** — иерархия специализированных субагентов (Researcher, Executor, Verifier, Planner, Memory Curator) под управлением Orchestrator.
- **Не static** — топология команды и стратегия планирования адаптируются под задачу.
- **Не tool-dependent** — абстракция над протоколами MCP (инструменты) и A2A (межагентное взаимодействие).

Подробности архитектуры, исследовательский ландшафт и план разработки по фазам — в [docs/](docs/).

## Быстрый старт

```powershell
git clone https://github.com/rusnetru/next-gen-agent.git
cd next-gen-agent
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest -q     # проверить, что всё работает
python src/main.py      # запустить агента
```

Полная инструкция по развёртыванию (разработка + сборка Windows .exe) — [docs/04_deployment.md](docs/04_deployment.md).

## Структура репозитория

```
next-gen-agent/
├── README.md
├── docs/
│   ├── 00_progress_log.md         # журнал выполнения плана по фазам (что сделано, коммиты)
│   ├── 01_research_landscape.md   # обзор существующих решений и подходов
│   ├── 02_development_plan.md     # план разработки по фазам (0-5)
│   ├── 03_tech_stack.md           # зафиксированный технологический стек
│   └── 04_deployment.md           # инструкция по развёртыванию
├── src/
│   ├── agent/                     # базовый agent loop (perceive-retrieve-plan-act-observe-store)
│   ├── memory/                    # episodic / semantic / procedural память + Memory API
│   ├── orchestrator/              # Orchestrator, субагенты, communication layer
│   ├── goals/                     # Goal Management System (иерархия целей)
│   ├── planning/                  # Planning Engine (ReAct+critique, MCTS, выбор стратегии)
│   ├── tasks/                     # персистентный task graph (DAG)
│   ├── loops/                     # self-correction loops (inner/outer/meta)
│   ├── evolution/                 # skill evolution, strategy adaptation, team composition learning
│   ├── observability/             # трейсинг действий, dashboard-снимок состояния
│   ├── safety/                    # memory safety guard, human-in-the-loop, self-modification limits
│   ├── scalability/                # async-исполнение субагентов
│   └── tools/                     # интеграции инструментов (MCP и др.)
├── tests/
├── build.ps1                      # сборка Windows-исполняемого файла (PyInstaller)
├── requirements.txt
└── pyproject.toml
```

## Документация

- [Журнал выполнения плана](docs/00_progress_log.md) — что сделано по каждой фазе, с коммитами
- [Обзор исследовательского ландшафта](docs/01_research_landscape.md)
- [План разработки](docs/02_development_plan.md)
- [Технологический стек](docs/03_tech_stack.md)
- [Развёртывание](docs/04_deployment.md)

## Статус разработки

Все 6 фаз плана пройдены в объёме, реализуемом как библиотечный код (Фаза 5 — частично: пункты, требующие реальной инфраструктуры — облачная БД, horizontal scaling — намеренно не реализовывались как код).
Модули памяти, оркестратора, целей/планирования и эволюции реализованы и протестированы, но пока не связаны в единый end-to-end сценарий, а субагенты — детерминированные заглушки без реальных вызовов LLM.
Подробности — в [docs/00_progress_log.md](docs/00_progress_log.md).

## Сборка под Windows

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\build.ps1
```

Результат — исполняемый файл `dist\next-gen-agent.exe`. Подробнее, включая развёртывание на машине без Python, — [docs/04_deployment.md](docs/04_deployment.md).
