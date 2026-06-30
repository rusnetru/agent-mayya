from src.goals.goal_stack import GoalStack
from src.memory.api import Memory
from src.observability.dashboard import snapshot
from src.observability.tracer import Tracer


def test_tracer_records_and_exports_events():
    tracer = Tracer()
    tracer.record("orchestrator", "dispatch", {"role": "researcher"})
    tracer.record("memory", "store", {"event": "hello"})

    assert len(tracer.events()) == 2
    assert len(tracer.by_component("orchestrator")) == 1
    exported = tracer.export()
    assert exported[0]["component"] == "orchestrator"
    assert exported[0]["action"] == "dispatch"


def test_tracer_clear_empties_events():
    tracer = Tracer()
    tracer.record("x", "y")
    tracer.clear()
    assert tracer.events() == []


def test_dashboard_snapshot_includes_memory_and_goals():
    memory = Memory(db_path=":memory:", consolidate_every=0)
    memory.store("hello world")
    memory.skills.extract("a", "do a")
    memory.skills.record_success("a")

    goals = GoalStack()
    goals.push("ship the agent", horizon="long_term")

    state = snapshot(memory, goals)
    assert state["episodic_count"] == 1
    assert "hello world" in state["working_memory"]
    assert state["skills"]["a"]["success_rate"] == 1.0
    assert state["active_goals"] == [{"description": "ship the agent", "horizon": "long_term"}]


def test_dashboard_snapshot_without_goals():
    memory = Memory(db_path=":memory:")
    state = snapshot(memory)
    assert "active_goals" not in state
