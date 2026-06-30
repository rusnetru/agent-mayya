"""Task-Decoupled Execution (Phase 3.3).

Separates "what to do" (the persistent task graph) from "how to execute it
right now" (the caller's execute function). Unfinished tasks survive process
restarts via SQLite, and dependencies form a DAG so independent branches can
run in parallel.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

Status = Literal["pending", "in_progress", "done", "failed"]


@dataclass
class TaskNode:
    id: int
    description: str
    status: Status
    depends_on: list[int]


class TaskGraph:
    def __init__(self, db_path: str | Path = "tasks.db") -> None:
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dependencies (
                task_id INTEGER NOT NULL,
                depends_on_id INTEGER NOT NULL
            )
            """
        )
        self._conn.commit()

    def add_task(self, description: str, depends_on: list[int] | None = None) -> TaskNode:
        cursor = self._conn.execute(
            "INSERT INTO tasks (description, status) VALUES (?, 'pending')", (description,)
        )
        task_id = cursor.lastrowid
        for dep_id in depends_on or []:
            self._conn.execute(
                "INSERT INTO dependencies (task_id, depends_on_id) VALUES (?, ?)", (task_id, dep_id)
            )
        self._conn.commit()
        return self.get(task_id)

    def get(self, task_id: int) -> TaskNode:
        row = self._conn.execute(
            "SELECT id, description, status FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        deps = [
            r[0]
            for r in self._conn.execute(
                "SELECT depends_on_id FROM dependencies WHERE task_id = ?", (task_id,)
            ).fetchall()
        ]
        return TaskNode(id=row[0], description=row[1], status=row[2], depends_on=deps)

    def set_status(self, task_id: int, status: Status) -> None:
        self._conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
        self._conn.commit()

    def ready_tasks(self) -> list[TaskNode]:
        """Pending tasks whose dependencies are all done — runnable now."""
        ready = []
        for row in self._conn.execute("SELECT id FROM tasks WHERE status = 'pending'").fetchall():
            task = self.get(row[0])
            deps_done = all(self.get(dep_id).status == "done" for dep_id in task.depends_on)
            if deps_done:
                ready.append(task)
        return ready

    def all_tasks(self) -> list[TaskNode]:
        ids = [r[0] for r in self._conn.execute("SELECT id FROM tasks ORDER BY id").fetchall()]
        return [self.get(i) for i in ids]

    def run_ready(self, execute: Callable[[TaskNode], bool]) -> int:
        """Execute all currently-ready tasks via `execute` (returns success bool).
        Returns count of tasks completed successfully in this pass.
        """
        completed = 0
        for task in self.ready_tasks():
            self.set_status(task.id, "in_progress")
            success = execute(task)
            self.set_status(task.id, "done" if success else "failed")
            if success:
                completed += 1
        return completed

    def close(self) -> None:
        self._conn.close()
