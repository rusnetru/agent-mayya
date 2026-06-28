from src.agent.loop import Agent


def test_agent_step_returns_result():
    agent = Agent()
    result = agent.step("hello")
    assert "hello" in result


def test_agent_stores_episode():
    agent = Agent()
    agent.step("hello")
    retrieved = agent.memory.retrieve("hello")
    assert len(retrieved) == 1
