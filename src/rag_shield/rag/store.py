"""Vector stores with separate namespaces (e.g. `vulnerable` and `defended`)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np

NAMESPACES = ("vulnerable", "defended")


@dataclass
class Hit:
    chunk_id: str
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class VectorStore(ABC):
    @abstractmethod
    def add(
        self,
        namespace: str,
        ids: list[str],
        texts: list[str],
        vectors: np.ndarray,
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None: ...

    @abstractmethod
    def query(self, namespace: str, vector: np.ndarray, k: int) -> list[Hit]: ...

    @abstractmethod
    def delete(self, namespace: str, ids: list[str]) -> None: ...

    @abstractmethod
    def ids(self, namespace: str) -> list[str]: ...


class SimpleStore(VectorStore):
    """In-memory cosine store. Ties keep insertion order, so results are deterministic."""

    def __init__(self) -> None:
        self._ns: dict[str, dict[str, tuple[str, np.ndarray, dict[str, Any]]]] = {}

    def add(self, namespace, ids, texts, vectors, metadatas=None):
        if not (len(ids) == len(texts) == len(vectors)):
            raise ValueError("ids, texts and vectors must have equal length")
        ns = self._ns.setdefault(namespace, {})
        metas = metadatas or [{} for _ in ids]
        for cid, text, vec, meta in zip(ids, texts, vectors, metas, strict=True):
            ns[cid] = (text, np.asarray(vec, dtype=np.float32), dict(meta))

    def query(self, namespace, vector, k):
        ns = self._ns.get(namespace, {})
        if not ns or k <= 0:
            return []
        ids = list(ns)
        mat = np.stack([ns[i][1] for i in ids])
        scores = mat @ np.asarray(vector, dtype=np.float32)
        order = np.argsort(-scores, kind="stable")[:k]
        return [Hit(ids[i], ns[ids[i]][0], float(scores[i]), ns[ids[i]][2]) for i in order]

    def delete(self, namespace, ids):
        ns = self._ns.get(namespace, {})
        for cid in ids:
            ns.pop(cid, None)

    def ids(self, namespace):
        return list(self._ns.get(namespace, {}))


class ChromaStore(VectorStore):  # pragma: no cover - optional dependency, not used by tests
    """ChromaDB-backed store; one collection per namespace."""

    def __init__(self, path: str | None = None) -> None:
        try:
            import chromadb
        except ImportError as e:
            raise RuntimeError("ChromaStore needs `pip install chromadb`") from e
        self._client = chromadb.PersistentClient(path) if path else chromadb.EphemeralClient()

    def _col(self, namespace: str):
        return self._client.get_or_create_collection(namespace, metadata={"hnsw:space": "cosine"})

    def add(self, namespace, ids, texts, vectors, metadatas=None):
        self._col(namespace).upsert(
            ids=ids,
            documents=texts,
            embeddings=[list(map(float, v)) for v in vectors],
            metadatas=metadatas or None,
        )

    def query(self, namespace, vector, k):
        res = self._col(namespace).query(query_embeddings=[list(map(float, vector))], n_results=k)
        metas = (res.get("metadatas") or [[{}] * len(res["ids"][0])])[0]
        return [
            Hit(cid, doc, 1.0 - float(dist), meta or {})
            for cid, doc, dist, meta in zip(
                res["ids"][0], res["documents"][0], res["distances"][0], metas, strict=True
            )
        ]

    def delete(self, namespace, ids):
        if ids:
            self._col(namespace).delete(ids=ids)

    def ids(self, namespace):
        return list(self._col(namespace).get()["ids"])
