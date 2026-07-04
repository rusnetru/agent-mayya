"""Evals — замер качества Mayya на фиксированных сценариях.

Запуск:  .venv\\Scripts\\python -m evals.run          (все сценарии)
         .venv\\Scripts\\python -m evals.run identity  (один сценарий)

Каждый сценарий — свежий агент (без общей истории). Проверки:
  contains_any — в ответе есть хотя бы одна из строк (без регистра)
  not_contains — в ответе нет ни одной из строк (запрещённые фразы)
  tool_used    — агент вызвал хотя бы один из инструментов
  regex        — ответ матчится regex'ом
  max_length   — ответ не длиннее N символов

Результат печатается таблицей и сохраняется в evals/results-<дата>.json —
сравнивай прогоны между собой после заметных изменений.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import sys
import time


def check(kind: str, values: list[str], reply: str, tools_used: list[str]) -> bool:
    low = reply.lower()
    if kind == "contains_any":
        return any(v.lower() in low for v in values)
    if kind == "not_contains":
        return not any(v.lower() in low for v in values)
    if kind == "tool_used":
        return any(v in tools_used for v in values)
    if kind == "regex":
        return any(re.search(v, reply) for v in values)
    if kind == "max_length":
        return len(reply) <= int(values[0])
    return False


def run_scenario(scenario: dict, client, tools: dict) -> dict:
    from src.agent.conversational import ConversationalAgent
    from src.memory.api import Memory

    agent = ConversationalAgent(client, memory=Memory(db_path=":memory:"), tools=tools)
    tools_used: list[str] = []

    def on_event(ev: dict) -> None:
        if ev["type"] == "tool":
            tools_used.append(ev["name"])

    prompts = scenario["prompt"] if isinstance(scenario["prompt"], list) else [scenario["prompt"]]
    reply = ""
    t0 = time.time()
    try:
        for p in prompts:
            reply = agent.chat(p, on_event=on_event)
        error = None
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
    elapsed = round(time.time() - t0, 1)

    if error:
        results = [{"check": "no_error", "passed": False}]
    else:
        results = [
            {"check": c["type"], "passed": check(c["type"], c["values"], reply, tools_used)}
            for c in scenario["checks"]
        ]
    return {
        "id": scenario["id"],
        "passed": all(r["passed"] for r in results),
        "checks": results,
        "tools_used": tools_used,
        "seconds": elapsed,
        "reply_head": reply[:200],
        "error": error,
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv()

    from src.llm.client import LLMClient
    from src.tools.registry import REGISTRY

    only = sys.argv[1] if len(sys.argv) > 1 else None
    base = os.path.dirname(__file__)
    with open(os.path.join(base, "scenarios.json"), encoding="utf-8") as f:
        scenarios = json.load(f)
    if only:
        scenarios = [s for s in scenarios if s["id"] == only]

    client = LLMClient()
    results = []
    for s in scenarios:
        r = run_scenario(s, client, dict(REGISTRY))
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"[{mark}] {r['id']:<22} {r['seconds']:>6}s  tools={','.join(r['tools_used']) or '-'}")
        if not r["passed"]:
            for c in r["checks"]:
                if not c["passed"]:
                    print(f"       failed check: {c['check']}")
            print(f"       reply: {r['reply_head'][:150]}")
        results.append(r)

    passed = sum(1 for r in results if r["passed"])
    print(f"\n{passed}/{len(results)} scenarios passed | model: {client.model}")

    out = {
        "date": datetime.datetime.now().isoformat(timespec="seconds"),
        "model": client.model,
        "passed": passed,
        "total": len(results),
        "results": results,
    }
    path = os.path.join(base, f"results-{datetime.date.today()}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"saved: {path}")

    # подчистить артефакт file_roundtrip
    if os.path.isfile("eval_tmp_note.txt"):
        os.remove("eval_tmp_note.txt")


if __name__ == "__main__":
    main()
