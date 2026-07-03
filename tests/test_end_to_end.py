from src.agent.end_to_end import EndToEndAgent
from src.memory.api import Memory


def test_run_succeeds_with_stub_subagents():
    agent = EndToEndAgent(memory=Memory(db_path=":memory:"))
    result = agent.run("research X and execute Y", task_class="demo")

    assert result.succeeded is True
    assert result.attempts == 1
    assert result.strategy in {"sequential", "parallel", "hierarchical"}
    assert result.orchestration["verified"] is True


def test_run_records_goal_and_trace_events():
    agent = EndToEndAgent(memory=Memory(db_path=":memory:"))
    agent.run("execute the deploy")

    assert agent.goals.roots[0].active is False
    components = {e.component for e in agent.tracer.events()}
    assert "end_to_end" in components
    assert "orchestrator" in components


def test_strategy_adapter_learns_across_runs():
    agent = EndToEndAgent(memory=Memory(db_path=":memory:"))
    agent.run("execute task one", task_class="ops")
    agent.run("execute task two", task_class="ops")

    selected = agent.strategy_adapter.select("ops")
    assert selected == "sequential"


def test_run_uses_llm_subagents_when_use_llm_true():
    from src.llm.subagent import LLMSubagent, LLMVerifier

    class FakeLLMClient:
        def complete(self, system_prompt, user_message, temperature=0.3):
            # Verifier prompt is the only one without role keywords
            if any(w in system_prompt.lower() for w in ("research", "researcher", "executor", "planner", "route", "router")):
                return "ok done"
            return "PASS"

    memory = Memory(db_path=":memory:")
    agent = EndToEndAgent(memory=memory, use_llm=True, llm_client=FakeLLMClient())

    assert isinstance(agent.orchestrator.pool["researcher"], LLMSubagent)
    assert isinstance(agent.orchestrator.pool["verifier"], LLMVerifier)

    result = agent.run("research market and execute plan")
    assert result.succeeded is True
