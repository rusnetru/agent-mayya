# Next Gen Agent — Cron tool (аналог cronjob из Hermes): задачи по расписанию.
#
# Хранилище — cron.json в корне проекта. Форматы расписания:
#   "every 10m" / "every 2h"   — повторять каждые N минут/часов
#   "daily 09:30"              — каждый день в HH:MM
#   "in 30m" / "in 2h"         — один раз через N минут/часов
#   "once 2026-07-05 18:00"    — один раз в указанное время
# Исполнение — фоновый поток в main.py; здесь только хранилище и расчёт времени.

from __future__ import annotations

import datetime
import json
import os
import re
import uuid

CRON_FILE = "cron.json"


def parse_schedule(schedule: str, now: datetime.datetime | None = None) -> tuple[float, bool]:
    """Return (next_run_timestamp, repeats). Raises ValueError on bad format."""
    now = now or datetime.datetime.now()
    s = schedule.strip().lower()

    m = re.fullmatch(r"every\s+(\d+)\s*(m|min|h|hour)s?", s)
    if m:
        minutes = int(m.group(1)) * (60 if m.group(2).startswith("h") else 1)
        if minutes < 1:
            raise ValueError("interval must be >= 1 minute")
        return (now + datetime.timedelta(minutes=minutes)).timestamp(), True

    m = re.fullmatch(r"daily\s+(\d{1,2}):(\d{2})", s)
    if m:
        hh, mm = int(m.group(1)), int(m.group(2))
        if hh > 23 or mm > 59:
            raise ValueError(f"bad time: {hh}:{mm:02d}")
        run = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if run <= now:
            run += datetime.timedelta(days=1)
        return run.timestamp(), True

    m = re.fullmatch(r"in\s+(\d+)\s*(m|min|h|hour)s?", s)
    if m:
        minutes = int(m.group(1)) * (60 if m.group(2).startswith("h") else 1)
        return (now + datetime.timedelta(minutes=minutes)).timestamp(), False

    m = re.fullmatch(r"once\s+(\d{4}-\d{2}-\d{2})\s+(\d{1,2}):(\d{2})", s)
    if m:
        run = datetime.datetime.strptime(f"{m.group(1)} {m.group(2)}:{m.group(3)}", "%Y-%m-%d %H:%M")
        if run <= now:
            raise ValueError("scheduled time is in the past")
        return run.timestamp(), False

    raise ValueError(
        f"bad schedule '{schedule}' — use: 'every 10m', 'daily 09:30', 'in 30m', 'once 2026-07-05 18:00'"
    )


class CronStore:
    def __init__(self, path: str = CRON_FILE) -> None:
        self.path = path

    def _load(self) -> list[dict]:
        if not os.path.isfile(self.path):
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return []

    def _save(self, jobs: list[dict]) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(jobs, f, ensure_ascii=False, indent=1)

    def create(self, schedule: str, task: str) -> dict:
        next_run, repeats = parse_schedule(schedule)
        job = {
            "id": uuid.uuid4().hex[:8],
            "schedule": schedule.strip(),
            "task": task.strip(),
            "next_run": next_run,
            "repeats": repeats,
            "last_run": None,
            "last_result": None,
        }
        jobs = self._load()
        jobs.append(job)
        self._save(jobs)
        return job

    def list(self) -> list[dict]:
        return self._load()

    def remove(self, job_id: str) -> bool:
        jobs = self._load()
        kept = [j for j in jobs if j["id"] != job_id]
        if len(kept) == len(jobs):
            return False
        self._save(kept)
        return True

    def due(self, now: float | None = None) -> list[dict]:
        now = now or datetime.datetime.now().timestamp()
        return [j for j in self._load() if j["next_run"] <= now]

    def mark_ran(self, job_id: str, result: str) -> None:
        """After a run: reschedule repeating jobs, drop one-shot jobs."""
        jobs = self._load()
        for job in list(jobs):
            if job["id"] != job_id:
                continue
            job["last_run"] = datetime.datetime.now().timestamp()
            job["last_result"] = result[:500]
            if job["repeats"]:
                job["next_run"], _ = parse_schedule(job["schedule"])
            else:
                jobs.remove(job)
        self._save(jobs)


def _fmt_ts(ts: float | None) -> str:
    if not ts:
        return "-"
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def cronjob(action: str, schedule: str = "", task: str = "", job_id: str = "") -> str:
    """Tool entrypoint: manage scheduled jobs. Returns JSON."""
    store = CronStore()
    try:
        if action == "create":
            if not schedule or not task:
                return json.dumps({"success": False, "error": "create requires schedule and task"}, ensure_ascii=False)
            job = store.create(schedule, task)
            return json.dumps(
                {"success": True, "id": job["id"], "next_run": _fmt_ts(job["next_run"]), "repeats": job["repeats"]},
                ensure_ascii=False,
            )
        if action == "list":
            jobs = [
                {
                    "id": j["id"],
                    "schedule": j["schedule"],
                    "task": j["task"],
                    "next_run": _fmt_ts(j["next_run"]),
                    "last_run": _fmt_ts(j["last_run"]),
                }
                for j in store.list()
            ]
            return json.dumps({"success": True, "jobs": jobs, "count": len(jobs)}, ensure_ascii=False)
        if action == "remove":
            ok = store.remove(job_id)
            return json.dumps({"success": ok, "id": job_id, "removed": ok}, ensure_ascii=False)
        return json.dumps({"success": False, "error": f"unknown action '{action}' — use create/list/remove"}, ensure_ascii=False)
    except ValueError as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)
