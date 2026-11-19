"""Embedders. HashEmbedder is deterministic and offline (tests); BgeEmbedder is the real one."""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod

import numpy as np

_TOKEN = re.compile(r"\w+", re.UNICODE)


class Embedder(ABC):
    model_id: str
    dim: int

    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an (n, dim) float32 array of L2-normalized vectors."""


def _normalize(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (m / norms).astype(np.float32)


class HashEmbedder(Embedder):
    """Signed feature hashing of lowercase word tokens. Same text -> same vector, always."""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim
        self.model_id = f"hash-embedder-v1-d{dim}"

    def embed(self, texts: list[str]) -> np.ndarray:
        m = np.zeros((len(texts), self.dim), dtype=np.float64)
        for row, text in enumerate(texts):
            for tok in _TOKEN.findall(text.lower()):
                h = int.from_bytes(hashlib.sha1(tok.encode("utf-8")).digest()[:8], "big")
                m[row, h % self.dim] += 1.0 if (h >> 63) & 1 else -1.0
        return _normalize(m)


class BgeEmbedder(Embedder):
    """BAAI/bge-small-en-v1.5 via sentence-transformers. Optional; not used by tests.
    Pin `revision` to an immutable commit hash for recorded runs."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", revision: str | None = None):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:  # pragma: no cover - optional dependency
            raise RuntimeError("BgeEmbedder needs `pip install sentence-transformers`") from e
        self._model = SentenceTransformer(model_name, revision=revision)
        self.dim = int(self._model.get_sentence_embedding_dimension())
        self.model_id = f"{model_name}@{revision or 'unpinned'}"

    def embed(self, texts: list[str]) -> np.ndarray:  # pragma: no cover - optional dependency
        vecs = self._model.encode(texts, normalize_embeddings=True)
        return np.asarray(vecs, dtype=np.float32)
