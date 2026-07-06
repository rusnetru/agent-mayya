"""
Kanban Bridge — живой мост между Mayya и Hermes через его Kanban-базу.

Что умеет:
- Забрать задачу из Kanban Hermes (по статусу/assignee)
- Создать задачу в Kanban Hermes (результат для Hermes)
- Обновить статус задачи (взял / сделал / ошибка)
- Комментировать задачу

Путь к БД Hermes: ~/AppData/Local/hermes/kanban.db
Путь к БД Mayya: tasks.db (своя)
"""

import sqlite3
import os
import time
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ─── Пути ───────────────────────────────────────────────────────────────

HERMES_KANBAN_DB = Path.home() / "AppData" / "Local" / "hermes" / "kanban.db"
MAYYA_TASKS_DB = Path(__file__).resolve().parent.parent / "tasks.db"
MAYYA_TENANT = "mayya"


# ─── Инициализация ──────────────────────────────────────────────────────

def _ensure_hermes_db():
    """Проверяем, что база Hermes существует и доступна."""
    if not HERMES_KANBAN_DB.exists():
        raise FileNotFoundError(f"Kanban Hermes не найден: {HERMES_KANBAN_DB}")


def _connect_hermes():
    """Читающее подключение к Kanban Hermes (без блокировки на запись)."""
    _ensure_hermes_db()
    conn = sqlite3.connect(str(HERMES_KANBAN_DB), timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def _connect_hermes_write():
    """Пишущее подключение к Kanban Hermes с retry."""
    _ensure_hermes_db()
    conn = sqlite3.connect(str(HERMES_KANBAN_DB), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _connect_mayya():
    """Своя БД для учёта обработанных задач."""
    conn = sqlite3.connect(str(MAYYA_TASKS_DB), timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_tasks (
            task_id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'new',
            taken_at INTEGER,
            completed_at INTEGER,
            result_summary TEXT,
            error TEXT
        )
    """)
    conn.commit()
    return conn


# ─── API для работы с задачами ──────────────────────────────────────────

def get_new_tasks(assignee: str = None, max_results: int = 5) -> list[dict]:
    """
    Забрать новые/открытые задачи из Kanban Hermes.
    Если assigne=None — любые незакреплённые.
    Если assigne=MAYYA_TENANT — только адресованные Mayya.
    """
    conn = _connect_hermes()
    try:
        where = "status IN ('backlog', 'todo', 'ready')"
        params = []
        if assignee:
            where += " AND assignee = ?"
            params.append(assignee)
        else:
            where += " AND (assignee IS NULL OR assignee = '')"

        rows = conn.execute(
            f"SELECT * FROM tasks WHERE {where} ORDER BY priority DESC, created_at ASC LIMIT ?",
            (*params, max_results)
        ).fetchall()

        return [dict(r) for r in rows]
    finally:
        conn.close()


def claim_task(task_id: str, worker: str = MAYYA_TENANT) -> bool:
    """
    Занять задачу (claim) — взять в работу.
    Возвращает True, если получилось.
    """
    conn = _connect_hermes_write()
    try:
        now = int(time.time())
        # Проверяем, что задача ещё не занята или истёк claim
        task = conn.execute(
            "SELECT claim_lock, claim_expires FROM tasks WHERE id = ?",
            (task_id,)
        ).fetchone()
        if not task:
            return False
        if task["claim_lock"] and task["claim_lock"] != worker and task["claim_expires"] > now:
            return False  # занята другим

        conn.execute(
            """UPDATE tasks SET
                assignee = ?,
                status = 'in_progress',
                claim_lock = ?,
                claim_expires = ?,
                started_at = ?,
                current_run_id = COALESCE(current_run_id, 0) + 1
            WHERE id = ?""",
            (worker, worker, now + 3600, now, task_id)
        )
        conn.commit()

        # Логируем событие
        conn.execute(
            "INSERT INTO task_events (task_id, kind, payload, created_at) VALUES (?, 'claimed', ?, ?)",
            (task_id, json.dumps({"by": worker, "at": now}), now)
        )
        conn.commit()
        return True
    finally:
        conn.close()


def complete_task(task_id: str, result: str, error: str = None):
    """Отметить задачу выполненной и записать результат."""
    conn = _connect_hermes_write()
    try:
        now = int(time.time())
        status = "failed" if error else "done"

        conn.execute(
            """UPDATE tasks SET
                status = ?,
                completed_at = ?,
                result = ?,
                last_failure_error = ?
            WHERE id = ?""",
            (status, now, result, error or "", task_id)
        )
        conn.commit()

        conn.execute(
            "INSERT INTO task_events (task_id, kind, payload, created_at) VALUES (?, ?, ?, ?)",
            (task_id, "completed" if not error else "failed",
             json.dumps({"result": result, "error": error, "at": now}), now)
        )
        conn.commit()
    finally:
        conn.close()


def add_comment(task_id: str, author: str, body: str):
    """Добавить комментарий к задаче Hermes."""
    conn = _connect_hermes_write()
    try:
        now = int(time.time())
        conn.execute(
            "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?, ?, ?, ?)",
            (task_id, author, body, now)
        )
        conn.commit()
    finally:
        conn.close()


def create_task(
    title: str,
    body: str = "",
    assignee: str = None,
    priority: int = 0,
    tenant: str = MAYYA_TENANT,
    project_id: str = None,
) -> str:
    """
    Создать задачу в Kanban Hermes (например, результат для Hermes).
    Возвращает ID созданной задачи.
    """
    conn = _connect_hermes_write()
    try:
        task_id = str(uuid.uuid4())[:8]
        now = int(time.time())
        conn.execute(
            """INSERT INTO tasks
                (id, title, body, assignee, status, priority, created_by,
                 created_at, workspace_kind, tenant, project_id)
            VALUES (?, ?, ?, ?, 'todo', ?, ?, ?, 'shared', ?, ?)""",
            (task_id, title, body, assignee, priority, tenant, now, tenant, project_id)
        )
        conn.commit()
        return task_id
    finally:
        conn.close()


# ─── Учёт обработанных Mayya задач ──────────────────────────────────────

def mark_processed(task_id: str, status: str, result_summary: str = None, error: str = None):
    """Запомнить, что мы обработали задачу."""
    conn = _connect_mayya()
    try:
        now = int(time.time())
        conn.execute(
            """INSERT OR REPLACE INTO processed_tasks
                (task_id, status, taken_at, completed_at, result_summary, error)
            VALUES (?, ?, COALESCE((SELECT taken_at FROM processed_tasks WHERE task_id = ?), ?),
                    ?, ?, ?)""",
            (task_id, status, task_id, now, now, result_summary, error)
        )
        conn.commit()
    finally:
        conn.close()


def is_already_processed(task_id: str) -> bool:
    """Проверить, не брали ли мы эту задачу раньше."""
    conn = _connect_mayya()
    try:
        row = conn.execute(
            "SELECT 1 FROM processed_tasks WHERE task_id = ?",
            (task_id,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def list_processed() -> list[dict]:
    """Показать историю обработанных задач."""
    conn = _connect_mayya()
    try:
        rows = conn.execute(
            "SELECT * FROM processed_tasks ORDER BY taken_at DESC LIMIT 20"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─── Высокоуровневый цикл «забрать → выполнить → отдать» ────────────────

def poll_and_execute(max_tasks: int = 3) -> list[dict]:
    """
    Полный цикл:
    1. Проверить новые задачи в Kanban Hermes
    2. Взять каждую в работу (claim)
    3. Вернуть список взятых задач для дальнейшего исполнения Mayya
    """
    results = []
    tasks = get_new_tasks(assignee=None, max_results=max_tasks)

    for task in tasks:
        task_id = task["id"]
        if is_already_processed(task_id):
            continue

        if claim_task(task_id):
            mark_processed(task_id, "in_progress")
            results.append(dict(task))
            add_comment(task_id, MAYYA_TENANT,
                        f"🤖 Mayya взяла задачу в работу ({datetime.now().isoformat()})")

    return results


def report_result(task_id: str, success: bool, summary: str, details: str = None):
    """Отчитаться о выполненной задаче обратно в Kanban."""
    if success:
        complete_task(task_id, details or summary)
        add_comment(task_id, MAYYA_TENANT,
                    f"✅ Mayya выполнила: {summary}")
    else:
        complete_task(task_id, summary, error=details)
        add_comment(task_id, MAYYA_TENANT,
                    f"❌ Mayya не смогла: {summary}\n{details or ''}")

    mark_processed(task_id, "done" if success else "failed", summary, details)


# ─── Диагностика ────────────────────────────────────────────────────────

def ping() -> dict:
    """Проверить связь с Kanban Hermes и показать статус."""
    status = {
        "hermes_db_exists": HERMES_KANBAN_DB.exists(),
        "mayya_db_exists": MAYYA_TASKS_DB.exists(),
        "hermes_tables": [],
        "pending_tasks": 0,
        "processed_count": 0,
    }

    if status["hermes_db_exists"]:
        try:
            conn = _connect_hermes()
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            status["hermes_tables"] = [t["name"] for t in tables]

            pending = conn.execute(
                "SELECT COUNT(*) as cnt FROM tasks WHERE status IN ('backlog','todo','ready')"
            ).fetchone()
            status["pending_tasks"] = pending["cnt"]
            conn.close()
        except Exception as e:
            status["hermes_error"] = str(e)

    if status["mayya_db_exists"]:
        try:
            conn = _connect_mayya()
            cnt = conn.execute("SELECT COUNT(*) as cnt FROM processed_tasks").fetchone()
            status["processed_count"] = cnt["cnt"]
            conn.close()
        except Exception as e:
            status["mayya_error"] = str(e)

    return status
