# 🤝 Пайплайн Mayya ↔ Hermes

## Архитектура взаимодействия

**Mayya** (живой диалоговый агент, Python, открытый код, 4 уровня памяти)
**Hermes** (скомпилированный бинарник `hermes.exe`, Kanban-диспетчер, desktop automation, 50+ навыков)

Общая LLM-модель: DeepSeek через api.deepseek.com

---

## Как устроен обмен

Оба агента живут на одном ПК. Общаются через **файловый Kanban** — общую SQLite-базу `kanban.db`.

```
Hermes ставит задачу в Kanban
       │
       ▼
Mayya (ручной запуск или cron, раз в 30м):
  poll_and_execute() → забирает новые задачи,
                       assign себе, выполняет
       │
       ▼
  report_result() → пишет результат обратно в Kanban
       │
       ▼
Hermes видит: статус changed, комментарий, result
```

### Типы задач, которыми обмениваемся

| Направление | Что передаётся |
|---|---|
| **Hermes → Mayya** | «исследуй тему X», «скрапь сайт Y», «напиши код Z», «прочитай и проанализируй» |
| **Mayya → Hermes** | «поставь на мониторинг», «запусти фоновый процесс», «сделай снапшот» |

---

## Код моста

**Файл:** `shared/kanban_bridge.py` (300+ строк)

Функции:
- `read_hermes_tasks(db_path, status_filter)` — читает задачи из Kanban Hermes
- `claim_task(db_path, task_id, agent_name, timeout_min=60)` — забирает задачу в работу
- `report_result(db_path, task_id, result_data)` — отмечает выполненной, пишет результат
- `create_task(...)` — создаёт задачу для Hermes
- `add_comment(...)` — комментирует задачу
- `get_task_by_title(db_path, title)` — находит задачу по названию
- `poll_and_execute(db_path, agent_name="mayya")` — полный цикл: проверить → забрать → выполнить → отчитаться

**Файл учёта:** `shared/tasks.db` — Mayya хранит, какие задачи уже обработала (чтобы не брать одно и то же дважды)

---

## Навык (инструкция для Mayya)

**Файл:** `skills/kanban-bridge/SKILL.md`

Содержит:
- Когда и как включать kanban-bridge
- Какой cron поставить
- Пример полного цикла: поиск → claim → выполнение → report

---

## Текущий статус

- ✅ Модуль-мост написан и протестирован
- ✅ База Hermes читается (таблицы: tasks, task_events, task_comments, task_runs)
- ✅ Тестовая задача создана и закрыта
- ✅ Задача от Hermes забрана через poll_and_execute, учтена в tasks.db
- ❌ **Не починен баг** в `report_result` — падает `'NoneType' object is not subscriptable` при записи результата (скорее всего None в одной из колонок)

---

## Что можно доработать

1. **Починить** багу в `report_result`
2. **Поставить cron** — Mayya проверяет Kanban каждые 30 минут (пока жива)
3. **Именованные assignee** — Hermes шлёт задачи с assignee=mayya, Mayya автоматом подхватывает
4. **Сделать демо** — создать реальную задачу от Hermes к Mayya и провести полный цикл

---

*Сохранено 5 июля 2026*
