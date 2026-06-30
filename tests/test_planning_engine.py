from src.planning.engine import StrategyRegistry, mcts_select_action, react_with_self_critique


def test_react_self_critique_succeeds_immediately_when_critique_passes():
    result = react_with_self_critique(
        task="say hello",
        act=lambda t: "hello",
        critique=lambda task, result: None,
    )
    assert result.final_result == "hello"
    assert result.attempts == 1
    assert result.critiques == []


def test_react_self_critique_retries_until_feedback_clears():
    attempts_seen = []

    def act(task: str) -> str:
        attempts_seen.append(task)
        return "draft" if len(attempts_seen) < 2 else "final"

    def critique(task: str, result: str) -> str | None:
        return None if result == "final" else "needs more detail"

    result = react_with_self_critique("write a doc", act, critique, max_iterations=5)
    assert result.final_result == "final"
    assert result.attempts == 2
    assert result.critiques == ["needs more detail"]


def test_react_self_critique_gives_up_after_max_iterations():
    result = react_with_self_critique(
        task="impossible",
        act=lambda t: "bad",
        critique=lambda task, result: "still bad",
        max_iterations=3,
    )
    assert result.attempts == 3
    assert len(result.critiques) == 3


def test_mcts_select_action_prefers_higher_reward_action():
    rewards = {"good": 0.9, "bad": 0.1}
    chosen = mcts_select_action(
        actions=["good", "bad"],
        simulate=lambda action: rewards[action],
        iterations=100,
        seed=42,
    )
    assert chosen == "good"


def test_strategy_registry_prefers_higher_success_rate():
    registry = StrategyRegistry()
    registry.record("coding_task", "react", True)
    registry.record("coding_task", "react", True)
    registry.record("coding_task", "mcts", False)

    best = registry.best_strategy("coding_task", ["react", "mcts"])
    assert best == "react"


def test_strategy_registry_falls_back_to_first_when_no_history():
    registry = StrategyRegistry()
    best = registry.best_strategy("unseen_task", ["a", "b"])
    assert best == "a"
