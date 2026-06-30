import asyncio

from src.memory.api import Memory
from src.orchestrator.orchestrator import Orchestrator
from src.scalability.async_execution import run_async


def test_run_async_executes_all_subtasks_and_verifies():
    orch = Orchestrator(memory=Memory(db_path=":memory:"))
    result = asyncio.run(run_async(orch, "research X and execute Y"))

    assert result["verified"] is True
    assert len(result["subtasks"]) == 2
    assert any("researcher" in line for line in result["transcript"])
    assert any("executor" in line for line in result["transcript"])
