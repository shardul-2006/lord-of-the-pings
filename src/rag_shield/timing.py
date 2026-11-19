"""Per-run stage timing. Nested stages are keyed by their path, e.g. 'ingest/layer1'."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

NON_MIDDLEWARE_STAGES = frozenset({"integrity", "llm_generation"})


@dataclass
class Timings:
    samples: dict[str, list[float]] = field(default_factory=dict)
    _stack: list[str] = field(default_factory=list)

    @property
    def ms(self) -> dict[str, float]:
        """Total milliseconds per stage path."""
        return {k: sum(v) for k, v in self.samples.items()}

    def middleware_ms(self) -> float:
        """Top-level stages that count toward the middleware latency budget. LLM generation
        and the decision-integrity check (extra LLM calls) are reported separately."""
        return sum(v for k, v in self.ms.items()
                   if "/" not in k and k not in NON_MIDDLEWARE_STAGES)

    def record(self, name: str, ms: float) -> None:
        self.samples.setdefault(name, []).append(ms)

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        self._stack.append(name)
        key = "/".join(self._stack)
        start = time.perf_counter()
        try:
            yield
        finally:
            self.record(key, (time.perf_counter() - start) * 1000.0)
            self._stack.pop()


_current: ContextVar[Timings | None] = ContextVar("rag_shield_timings", default=None)


@contextmanager
def run() -> Iterator[Timings]:
    """Start a new per-run timing dict; `stage()` calls inside record into it."""
    timings = Timings()
    token = _current.set(timings)
    try:
        yield timings
    finally:
        _current.reset(token)


@contextmanager
def stage(name: str, timings: Timings | None = None) -> Iterator[None]:
    """Record a stage into `timings`, else the active run, else do nothing."""
    target = timings or _current.get()
    if target is None:
        yield
        return
    with target.stage(name):
        yield
