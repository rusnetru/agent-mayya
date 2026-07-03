# Next Gen Agent — ChromaDB-backed vector index (semantic embeddings)

from __future__ import annotations

import chromadb


class ChromaVectorIndex:
    """Drop-in replacement for VectorIndex using ChromaDB with real embeddings.

    Interface is identical: add(item_id, text), remove(item_id), search(query, top_k).
    Embeds via ChromaDB's default sentence-transformer (all-MiniLM-L6-v2).
    """

    def __init__(self, persist_dir: str | None = None) -> None:
        if persist_dir:
            self._client = chromadb.PersistentClient(path=persist_dir)
        else:
            self._client = chromadb.Client()
        self._collection = self._client.get_or_create_collection("episodes")

    def add(self, item_id: int, text: str) -> None:
        self._collection.upsert(
            ids=[str(item_id)],
            documents=[text],
        )

    def remove(self, item_id: int) -> None:
        try:
            self._collection.delete(ids=[str(item_id)])
        except Exception:
            pass

    def search(self, query: str, top_k: int = 5) -> list[tuple[int, float]]:
        results = self._collection.query(query_texts=[query], n_results=top_k)
        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]
        scored = []
        for id_str, dist in zip(ids, distances):
            scored.append((int(id_str), 1.0 / (1.0 + dist)))
        scored.sort(key=lambda p: p[1], reverse=True)
        return scored
