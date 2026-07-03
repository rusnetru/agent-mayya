"""Semantic memory — graph of consolidated facts, backed by NetworkX.

Versioning (Phase 1.2, SSGM-inspired): updating a fact never overwrites the
existing node in place. Instead a new versioned node is added and linked to
the old one via a `supersedes` edge, so stale-but-once-true facts remain
auditable instead of silently vanishing (stability + safety against drift).
"""

from __future__ import annotations

from typing import Any

import networkx as nx


class SemanticGraph:
    def __init__(self) -> None:
        self._graph = nx.DiGraph()
        self._versions: dict[str, int] = {}

    def add_fact(self, fact: str, metadata: dict[str, Any] | None = None) -> None:
        self._graph.add_node(fact, version=1, **(metadata or {}))
        self._versions[fact] = 1

    def has_fact(self, fact: str) -> bool:
        return self._graph.has_node(fact)

    def query(self, query: str, top_k: int = 5) -> list[str]:
        matches = [n for n in self._graph.nodes if query.lower() in n.lower()]
        return matches[:top_k]

    def link(self, fact_a: str, fact_b: str, relation: str) -> None:
        self._graph.add_edge(fact_a, fact_b, relation=relation)

    def update_fact(self, old_fact: str, new_fact: str, metadata: dict[str, Any] | None = None) -> None:
        """Supersede `old_fact` with `new_fact` without deleting the old node."""
        version = self._versions.get(old_fact, 1) + 1
        self._graph.add_node(new_fact, version=version, **(metadata or {}))
        self._versions[new_fact] = version
        self._graph.add_edge(new_fact, old_fact, relation="supersedes")

    def history(self, fact: str) -> list[str]:
        """Walk the supersedes chain backwards from `fact` to its origin."""
        chain = [fact]
        current = fact
        while True:
            successors = [
                target for _, target, data in self._graph.out_edges(current, data=True)
                if data.get("relation") == "supersedes"
            ]
            if not successors:
                break
            current = successors[0]
            chain.append(current)
        return chain

    def save(self, path: str) -> None:
        """Persist semantic graph to a JSON file."""
        from src.memory.json_store import save_graph_to_json

        save_graph_to_json(self._graph, path)

    def load(self, path: str) -> None:
        """Load semantic graph from a JSON file (merges into existing graph)."""
        from src.memory.json_store import load_graph_from_json

        loaded = load_graph_from_json(path)
        self._graph = nx.compose(self._graph, loaded)
        for node in loaded.nodes:
            self._versions[node] = loaded.nodes[node].get("version", 1)
