import datetime
import json

import pytest

from src.tools.cron import CronStore, cronjob, parse_schedule

NOW = datetime.datetime(2026, 7, 4, 12, 0, 0)


def test_parse_every_minutes():
    ts, repeats = parse_schedule("every 10m", now=NOW)
    assert repeats is True
    assert ts == (NOW + datetime.timedelta(minutes=10)).timestamp()


def test_parse_every_hours():
    ts, repeats = parse_schedule("every 2h", now=NOW)
    assert repeats is True
    assert ts == (NOW + datetime.timedelta(hours=2)).timestamp()


def test_parse_daily_today_and_tomorrow():
    ts, repeats = parse_schedule("daily 18:30", now=NOW)
    assert repeats is True
    assert datetime.datetime.fromtimestamp(ts) == NOW.replace(hour=18, minute=30)

    ts, _ = parse_schedule("daily 09:00", now=NOW)  # 09:00 already passed today
    assert datetime.datetime.fromtimestamp(ts) == NOW.replace(hour=9) + datetime.timedelta(days=1)


def test_parse_one_shots():
    ts, repeats = parse_schedule("in 30m", now=NOW)
    assert repeats is False
    assert ts == (NOW + datetime.timedelta(minutes=30)).timestamp()

    ts, repeats = parse_schedule("once 2026-07-05 08:15", now=NOW)
    assert repeats is False
    assert datetime.datetime.fromtimestamp(ts) == datetime.datetime(2026, 7, 5, 8, 15)


def test_parse_rejects_garbage_and_past():
    with pytest.raises(ValueError):
        parse_schedule("whenever", now=NOW)
    with pytest.raises(ValueError):
        parse_schedule("once 2020-01-01 00:00", now=NOW)
    with pytest.raises(ValueError):
        parse_schedule("daily 25:99", now=NOW)


def test_store_create_due_and_reschedule(tmp_path):
    store = CronStore(path=str(tmp_path / "cron.json"))
    job = store.create("every 5m", "проверить почту")

    assert store.due(now=job["next_run"] - 1) == []
    due = store.due(now=job["next_run"] + 1)
    assert [j["id"] for j in due] == [job["id"]]

    store.mark_ran(job["id"], "done")
    jobs = store.list()
    assert len(jobs) == 1  # repeating job stays, rescheduled forward
    assert jobs[0]["next_run"] >= job["next_run"]
    assert store.due() == []  # rescheduled ~5m into the future — not due right now
    assert jobs[0]["last_result"] == "done"


def test_store_one_shot_removed_after_run(tmp_path):
    store = CronStore(path=str(tmp_path / "cron.json"))
    job = store.create("in 1m", "разовая задача")
    store.mark_ran(job["id"], "ok")
    assert store.list() == []


def test_store_remove(tmp_path):
    store = CronStore(path=str(tmp_path / "cron.json"))
    job = store.create("every 1h", "t")
    assert store.remove(job["id"]) is True
    assert store.remove("nope") is False
    assert store.list() == []


def test_cronjob_tool_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # cron.json создаётся в cwd

    created = json.loads(cronjob("create", schedule="every 15m", task="дайджест новостей"))
    assert created["success"] is True and created["repeats"] is True

    listed = json.loads(cronjob("list"))
    assert listed["count"] == 1
    assert listed["jobs"][0]["task"] == "дайджест новостей"

    removed = json.loads(cronjob("remove", job_id=created["id"]))
    assert removed["success"] is True

    bad = json.loads(cronjob("create", schedule="каждый вторник", task="x"))
    assert bad["success"] is False

    unknown = json.loads(cronjob("explode"))
    assert unknown["success"] is False
