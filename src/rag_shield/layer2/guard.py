"""Guard models: the deeper second-pass scorer for escalated chunks.

- RuleGuard (default): NO deep model. Re-scores a sentence with the linguistic cues and the
  calibrated classifier. Its model id says so; use it when a deep model is unavailable.
- FakeGuard (tests): RuleGuard with knobs for fixed scores, failure and delay.
- DebertaGuard (optional real run): Hugging Face prompt-injection classifier, lazy-loaded, with
  a pinned immutable revision and a per-text cache.
Callers enforce the timeout; any guard error or timeout makes the scan `scan_failed`.
"""

from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod

from rag_shield.layer2.classifier import SentenceClassifier, default_classifier
from rag_shield.layer2.linguistic import cues_for, score_text

DEBERTA_MODEL = "protectai/deberta-v3-base-prompt-injection-v2"
DEBERTA_REVISION = "90c9989b1a342275dd0d1a95aad283c04e075671"  # immutable HF commit, Apache-2.0


class Guard(ABC):
    model_id: str

    @abstractmethod
    def score(self, sentences: list[str], contexts: list[str]) -> list[float]:
        """Injection probability per sentence; `contexts` holds neighbouring text."""


class RuleGuard(Guard):
    model_id = "rule-guard-v1 (no deep model)"

    def __init__(self, classifier: SentenceClassifier | None = None,
                 policy: dict | None = None) -> None:
        self.classifier = classifier
        self.cues = cues_for(policy)  # the policy's cue set, incl. domain-adapter cues

    def score(self, sentences, contexts):
        clf = self.classifier or default_classifier()
        probs = clf.predict_proba(sentences)
        return [max(float(p), score_text(s, self.cues).score)
                for p, s in zip(probs, sentences, strict=True)]


class FakeGuard(RuleGuard):
    model_id = "fake-guard (test double)"

    def __init__(self, fixed: float | None = None, fail: bool = False, delay_s: float = 0.0,
                 classifier: SentenceClassifier | None = None, policy: dict | None = None) -> None:
        super().__init__(classifier, policy)
        self.fixed, self.fail, self.delay_s = fixed, fail, delay_s
        self.calls = 0

    def score(self, sentences, contexts):
        self.calls += 1
        if self.delay_s:
            time.sleep(self.delay_s)
        if self.fail:
            raise RuntimeError("fake guard failure")
        if self.fixed is not None:
            return [self.fixed] * len(sentences)
        return super().score(sentences, contexts)


class DebertaGuard(Guard):  # pragma: no cover - optional dependency, not used by tests
    def __init__(self, model: str = DEBERTA_MODEL, revision: str | None = None) -> None:
        self.model = model
        self.revision = (revision or os.environ.get("RAG_SHIELD_GUARD_REVISION")
                         or (DEBERTA_REVISION if model == DEBERTA_MODEL else None))
        if not self.revision:
            raise RuntimeError("DebertaGuard needs a pinned revision (RAG_SHIELD_GUARD_REVISION)")
        self.model_id = f"{model}@{self.revision}"
        self._pipe = None
        self._cache: dict[str, float] = {}

    def _load(self):
        if self._pipe is None:
            try:
                from transformers import pipeline
            except ImportError as e:
                raise RuntimeError("DebertaGuard needs `pip install transformers torch`") from e
            self._pipe = pipeline(
                "text-classification", model=self.model, revision=self.revision, truncation=True
            )
        return self._pipe

    def score(self, sentences, contexts):
        todo = [s for s in sentences if s not in self._cache]
        if todo:
            for text, out in zip(todo, self._load()(todo), strict=True):
                p = out["score"] if out["label"].upper() == "INJECTION" else 1.0 - out["score"]
                self._cache[text] = float(p)
        return [self._cache[s] for s in sentences]


def make_guard(kind: str | None = None, policy: dict | None = None) -> Guard:
    """`policy` gives RuleGuard the policy's cue set (multilingual and domain cues)."""
    kind = os.environ.get("RAG_SHIELD_GUARD") or kind or "rule"
    if kind == "rule":
        return RuleGuard(policy=policy)
    if kind == "deberta":
        return DebertaGuard()
    raise ValueError(f"unknown guard kind {kind!r}")
