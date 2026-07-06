# Kanban Bridge — Живое взаимодействие с Hermes

## Когда использовать
- Пользователь сказал «работай с Hermes», «пайплайн», «общий Kanban», «забери задачу из Hermes»
- Нужно передать результат Hermes или получить от него задачу
- Диагностика связи с Hermes Kanban

## Что делает
Соединяет Mayya и Hermes через общую Kanban-базу Hermes (`kanban.db`).
Mayya может забирать задачи из очереди Hermes, выполнять их и отдавать результат обратно.

## Файлы
- `shared/kanban_bridge.py` — библиотека-мост (все функции)
- `tasks.db` — локальный учёт Mayya, какие задачи уже обработаны

## Основные операции

### 1. Проверить связь
```python
from shared.kanban_bridge import ping
status = ping()
```
Показывает: есть ли база Hermes, сколько задач в очереди, сколько уже обработано.

### 2. Забрать новые задачи
```python
from shared.kanban_bridge import poll_and_execute
tasks = poll_and_execute(max_tasks=3)
# tasks = [{"id": "...", "title": "...", "body": "...", ...}, ...]
```
Автоматически claim'ит задачи и помечает как взятые.

### 3. Выполнить задачу и отчитаться
```python
from shared.kanban_bridge import report_result

# Если успешно:
report_result(task_id="abc123", success=True,
              summary="Нашёл информацию по X", details="Подробный результат...")

# Если ошибка:
report_result(task_id="abc123", success=False,
              summary="Не удалось выполнить", details="Причина: ...")
```

### 4. Создать задачу для Hermes
```python
from shared.kanban_bridge import create_task

task_id = create_task(
    title="Проверить что-то",
    body="Описание задачи для Hermes",
    assignee="hermes",
    priority=1
)
```

### 5. Комментировать
```python
from shared.kanban_bridge import add_comment
add_comment(task_id, "mayya", "Уточнение: данные в файле report.md")
```

## Пример полного цикла

```python
from shared.kanban_bridge import poll_and_execute, report_result

# Забрать задачи
inbox = poll_and_execute(max_tasks=2)
for task in inbox:
    task_id = task["id"]
    print(f"Взяла: {task['title']}")

    # --- тут Mayya делает свою работу ---
    result = execute_task_logic(task)

    # Отчитаться
    report_result(task_id, result["success"], result["summary"], result.get("details"))
```

## Безопасность
- Мост открывает **только read+write к kanban.db**, никаких других файлов Hermes
- Не может запускать Hermes или менять его конфиг
- Все изменения логируются в `task_events` внутри kanban.db — Hermes видит, кто что делал
