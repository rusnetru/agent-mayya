from src.goals.goal_stack import GoalStack


def test_push_creates_root_goal():
    stack = GoalStack()
    goal = stack.push("build the agent", horizon="long_term")
    assert goal in stack.roots
    assert goal.active is True


def test_decompose_creates_subgoals_one_horizon_down():
    stack = GoalStack()
    goal = stack.push("build the agent", horizon="long_term")
    subgoals = stack.decompose(goal, ["design memory", "design orchestrator"])
    assert [g.horizon for g in subgoals] == ["mid_term", "mid_term"]
    assert goal.children == subgoals


def test_decompose_action_horizon_raises():
    stack = GoalStack()
    goal = stack.push("press the button", horizon="action")
    try:
        stack.decompose(goal, ["x"])
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_revise_updates_description_and_active_flag():
    stack = GoalStack()
    goal = stack.push("old goal")
    stack.revise(goal, new_description="new goal", active=False)
    assert goal.description == "new goal"
    assert goal.active is False


def test_active_leaves_returns_innermost_active_goals():
    stack = GoalStack()
    root = stack.push("long term", horizon="long_term")
    mid = stack.decompose(root, ["mid term"])[0]
    task = stack.decompose(mid, ["task"])[0]

    leaves = stack.active_leaves()
    assert leaves == [task]


def test_active_leaves_skips_inactive_branches():
    stack = GoalStack()
    root = stack.push("long term", horizon="long_term")
    mid1, mid2 = stack.decompose(root, ["mid 1", "mid 2"])
    stack.revise(mid1, active=False)

    leaves = stack.active_leaves()
    assert leaves == [mid2]
