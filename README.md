# Next Gen Agent

ИИ-агент нового поколения: постоянная память, иерархическая команда субагентов,
самоорганизующиеся goal/loop циклы и способность эволюционировать в процессе работы.

## Ключевые архитектурные принципы

- **Не stateless** — агент помнит контекст между сессиями (episodic + semantic memory).
- **Не monolithic** — иерархия специализированных субагентов (Researcher, Executor, Verifier, Planner, Memory Curator) под управлением Orchestrator.
- **Не static** — топология команды и стратегия планирования адаптируются под задачу.
- **Не tool-dependent** — абстракция над протоколами MCP (инструменты) и A2A (межагентное взаимодействие).

Подробности архитектуры, исследовательский ландшафт и план разработки по фазам — в [docs/](docs/).

## Структура репозитория

```
next-gen-agent/
├── README.md
├── docs/
│   ├── 01_research_landscape.md   # обзор существующих решений и подходов
│   └── 02_development_plan.md     # план разработки по фазам (0-5)
├── src/
│   ├── agent/                     # базовый agent loop (perceive-retrieve-plan-act-observe-store)
│   ├── memory/                    # episodic / semantic / procedural память
│   ├── orchestrator/              # оркестратор и управление субагентами
│   └── tools/                     # интеграции инструментов (MCP и др.)
├── tests/
├── build.ps1                      # сборка Windows-исполняемого файла (PyInstaller)
├── requirements.txt
└── pyproject.toml
```

## Документация

- [Обзор исследовательского ландшафта](docs/01_research_landscape.md)
- [План разработки](docs/02_development_plan.md)

## Статус разработки

Проект находится на **Фазе 0: Фундамент** — выбор стека, базовый agent loop, память v1.
См. [план разработки](docs/02_development_plan.md) для деталей по фазам.

## Сборка под Windows

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\build.ps1
```

Результат — исполняемый файл `dist\next-gen-agent.exe`.
