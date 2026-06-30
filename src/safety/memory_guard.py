"""Memory Safety Guard (Phase 5.2, SSGM-inspired).

Defends the semantic graph against drift and poisoning: a fact below a
confidence threshold, or one that directly contradicts an existing fact for
the same subject, is quarantined instead of written straight into semantic
memory. Quarantined facts stay inspectable/approvable rather than silently
dropped or silently trusted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.memory.semantic import SemanticGraph


@dataclass
class QuarantinedFact:
    fact: str
    metadata: dict[str, Any]
    reason: str


class MemorySafetyGuard:
    def __init__(self, semantic: SemanticGraph, min_confidence: float = 0.5) -> None:
        self.semantic = semantic
        self.min_confidence = min_confidence
        self.quarantine: list[QuarantinedFact] = []

    def propose_fact(self, fact: str, metadata: dict[str, Any] | None = None, contradicts: str | None = None) -> bool:
        """Attempt to write a fact. Returns True if accepted, False if quarantined."""
        metadata = metadata or {}
        confidence = metadata.get("confidence", 1.0)

        if confidence < self.min_confidence:
            self.quarantine.append(QuarantinedFact(fact, metadata, reason="low_confidence"))
            return False

        if contradicts is not None and self.semantic.has_fact(contradicts):
            self.quarantine.append(QuarantinedFact(fact, metadata, reason=f"contradicts:{contradicts}"))
            return False

        self.semantic.add_fact(fact, metadata)
        return True

    def release(self, fact: str) -> bool:
        """Human/operator override: force a quarantined fact into semantic memory."""
        for item in list(self.quarantine):
            if item.fact == fact:
                self.semantic.add_fact(item.fact, item.metadata)
                self.quarantine.remove(item)
                return True
        return False
