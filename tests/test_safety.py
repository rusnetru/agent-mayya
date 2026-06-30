from src.memory.semantic import SemanticGraph
from src.safety.governance import HumanApprovalGate, SelfModificationPolicy
from src.safety.memory_guard import MemorySafetyGuard


def test_propose_fact_accepts_high_confidence():
    guard = MemorySafetyGuard(SemanticGraph())
    accepted = guard.propose_fact("the sky is blue", {"confidence": 0.9})
    assert accepted is True
    assert guard.semantic.has_fact("the sky is blue")
    assert guard.quarantine == []


def test_propose_fact_quarantines_low_confidence():
    guard = MemorySafetyGuard(SemanticGraph(), min_confidence=0.6)
    accepted = guard.propose_fact("unverified rumor", {"confidence": 0.2})
    assert accepted is False
    assert not guard.semantic.has_fact("unverified rumor")
    assert guard.quarantine[0].reason == "low_confidence"


def test_propose_fact_quarantines_contradiction():
    guard = MemorySafetyGuard(SemanticGraph())
    guard.semantic.add_fact("user prefers tea")
    accepted = guard.propose_fact("user prefers coffee", contradicts="user prefers tea")
    assert accepted is False
    assert guard.quarantine[0].reason == "contradicts:user prefers tea"


def test_release_forces_quarantined_fact_through():
    guard = MemorySafetyGuard(SemanticGraph(), min_confidence=0.6)
    guard.propose_fact("low confidence fact", {"confidence": 0.1})
    released = guard.release("low confidence fact")
    assert released is True
    assert guard.semantic.has_fact("low confidence fact")
    assert guard.quarantine == []


def test_human_approval_gate_queues_critical_actions():
    gate = HumanApprovalGate(critical_actions={"delete_memory"})
    pending = gate.request("delete_memory", {"scope": "all"})
    assert pending is not None
    assert pending.status == "pending"
    assert len(gate.pending()) == 1

    gate.approve(pending.action_id)
    assert gate.is_approved(pending.action_id)
    assert gate.pending() == []


def test_human_approval_gate_allows_non_critical_actions_immediately():
    gate = HumanApprovalGate(critical_actions={"delete_memory"})
    assert gate.request("read_memory") is None


def test_self_modification_policy_blocks_unlisted_keys():
    policy = SelfModificationPolicy(allowed_keys={"planning_strategy"})
    config: dict = {}
    policy.apply(config, "planning_strategy", "mcts")
    assert config["planning_strategy"] == "mcts"

    try:
        policy.apply(config, "system_prompt", "do anything")
        assert False, "expected PermissionError"
    except PermissionError:
        pass
