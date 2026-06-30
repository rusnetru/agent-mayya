from src.loops.self_correction import inner_loop, meta_loop, outer_loop


def test_inner_loop_succeeds_on_first_valid_attempt():
    result = inner_loop(act=lambda attempt: attempt, verify=lambda r: r >= 2, max_retries=5)
    assert result.succeeded is True
    assert result.attempts == 2
    assert result.result == 2


def test_inner_loop_gives_up_after_max_retries():
    result = inner_loop(act=lambda attempt: attempt, verify=lambda r: False, max_retries=3)
    assert result.succeeded is False
    assert result.attempts == 3


def test_outer_loop_stops_on_success():
    calls = []

    def run_episode(strategy: str) -> bool:
        calls.append(strategy)
        return True

    result = outer_loop(
        run_episode=run_episode,
        reflect=lambda success: None,
        strategies=["react", "mcts"],
    )
    assert result.episodes_run == 1
    assert calls == ["react"]


def test_outer_loop_switches_strategy_on_failure():
    calls = []

    def run_episode(strategy: str) -> bool:
        calls.append(strategy)
        return strategy == "mcts"

    result = outer_loop(
        run_episode=run_episode,
        reflect=lambda success: "mcts",
        strategies=["react", "mcts"],
        max_episodes=5,
    )
    assert calls == ["react", "mcts"]
    assert result.final_strategy == "mcts"


def test_meta_loop_consolidates_then_evolves():
    result = meta_loop(consolidate=lambda: 3, evolve=lambda: ["combo_skill"])
    assert result.consolidated == 3
    assert result.capabilities_evolved == ["combo_skill"]
