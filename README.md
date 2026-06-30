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

Развёртывание — через git-клон, не через отдельный `.exe`. Это даёт встроенный путь обновления: `git pull` подтягивает новый код без переустановки.

```powershell
git clone https://github.com/rusnetru/next-gen-agent.git
cd next-gen-agent
.\install.ps1            # venv + зависимости
.\.venv\Scripts\python.exe -m pytest -q   # проверить, что всё работает
.\.venv\Scripts\python.exe src\main.py    # запустить агента
```

Обновление до последней версии:

```powershell
.\update.ps1
```

`update.ps1` делает `git pull --ff-only` и переустанавливает зависимости, если изменился `requirements.txt`; отказывается обновлять поверх незакоммиченных локальных правок. Та же логика доступна агенту программно — `src/update/self_update.py` (агент может сам проверять и подтягивать обновления своего кода).

Полная инструкция, включая опциональную сборку Windows `.exe`, — [docs/04_deployment.md](docs/04_deployment.md).

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
│   ├── update/                     # git-based self-update (Phase deploy)
│   └── tools/                     # интеграции инструментов (MCP и др.)
├── tests/
├── install.ps1                    # первичная установка: venv + зависимости
├── update.ps1                     # обновление: git pull + переустановка зависимостей при необходимости
├── build.ps1                      # опционально: сборка Windows .exe (PyInstaller)
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

## Сборка отдельного .exe (опционально, не основной путь)

Для случаев, когда на целевой машине принципиально не ставить Python/git:

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\build.ps1
```

Результат — `dist\next-gen-agent.exe`. У такого файла нет обновления через git — для обновления его нужно пересобирать заново. Штатный путь развёртывания и обновления — git-клон, см. выше и [docs/04_deployment.md](docs/04_deployment.md).
