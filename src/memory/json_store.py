# Next Gen Agent — Semantic memory: JSON persistence for SemanticGraph

import json
import os
import networkx as nx


def save_graph_to_json(graph: nx.DiGraph, path: str) -> None:
    """Persist a NetworkX DiGraph to a JSON file."""
    data = {
        "nodes": [(n, graph.nodes[n]) for n in graph.nodes],
        "edges": [(u, v, graph.edges[u, v]) for u, v in graph.edges],
    }

    class _Encoder(json.JSONEncoder):
        def default(self, o):
            return str(o)

    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, cls=_Encoder, ensure_ascii=False)


def load_graph_from_json(path: str) -> nx.DiGraph:
    """Load a NetworkX DiGraph from a JSON file."""
    g = nx.DiGraph()
    if not os.path.isfile(path):
        return g
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for node, attrs in data.get("nodes", []):
        g.add_node(node, **attrs)
    for u, v, attrs in data.get("edges", []):
        g.add_edge(u, v, **attrs)
    return g
