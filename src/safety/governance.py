"""Human-in-the-loop gate and self-modification limits (Phase 5.2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PendingAction:
    action_id: int
    action: str
    payload: dict[str, Any]
    status: str = "pending"  # pending | approved | rejected


class HumanApprovalGate:
    """Critical actions are queued instead of executed immediately; an operator
    must approve or reject them before they can run.
    """

    def __init__(self, critical_actions: set[str]) -> None:
        self.critical_actions = critical_actions
        self._next_id = 1
        self._queue: dict[int, PendingAction] = {}

    def is_critical(self, action: str) -> bool:
        return action in self.critical_actions

    def request(self, action: str, payload: dict[str, Any] | None = None) -> PendingAction | None:
        """Returns a PendingAction needing approval, or None if the action can run immediately."""
        if not self.is_critical(action):
            return None
        pending = PendingAction(action_id=self._next_id, action=action, payload=payload or {})
        self._queue[pending.action_id] = pending
        self._next_id += 1
        return pending

    def approve(self, action_id: int) -> None:
        self._queue[action_id].status = "approved"

    def reject(self, action_id: int) -> None:
        self._queue[action_id].status = "rejected"

    def is_approved(self, action_id: int) -> bool:
        return self._queue[action_id].status == "approved"

    def pending(self) -> list[PendingAction]:
        return [p for p in self._queue.values() if p.status == "pending"]


class SelfModificationPolicy:
    """Restricts adaptive behavior (Phase 4) to a fixed, declared set of
    configuration keys — the agent can change *values* for these keys but
    can never introduce or execute new ones, i.e. it tunes config, not code.
    """

    def __init__(self, allowed_keys: set[str]) -> None:
        self.allowed_keys = allowed_keys

    def validate(self, key: str) -> None:
        if key not in self.allowed_keys:
            raise PermissionError(f"self-modification of '{key}' is not permitted")

    def apply(self, config: dict[str, Any], key: str, value: Any) -> None:
        self.validate(key)
        config[key] = value
