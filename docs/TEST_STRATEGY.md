# RAG-Shield Test Strategy

> Skeleton (Phase 0).

## Principles
- Every phase ends with `bash scripts/verify_phase.sh N`, which is cumulative: ruff, then the
  tests of phases 0…N, then the smoke scripts of phases 0…N.
- Tests are deterministic and offline: `MockLLM` and the hash embedder. No network, no model
  downloads.
- `MockLLM` is a test double. Its outputs are **not** evidence about real LLM behaviour.
- Scanner errors are errors: tests assert that bad inputs are never `clean`.
- A test is only changed when the test itself is wrong, and the reason is recorded.

## Split rule (Spec G)
- Datasets are split **by template** into train / dev / test.
- Related templates and attack variants never appear in more than one split.
- Thresholds and calibration are tuned on **dev only**; test is never used for tuning.

## Metrics definitions
- **ASR:** per task, written attack goal and success rubric; numerator and denominator shown.
- **FPR:** denominator is benign examples only.
- **Fact retention:** against pre-labelled facts, not sentence counts.
- **Gate escape rate:** attacks the fast first pass let through without escalation.
- **Latency:** nearest-rank p50/p95 on named hardware with sample count, cold/warm flag, and
  whether model load is included. Ingestion, query, LLM generation and integrity mode separate.

## Per-phase test directories
`tests/phase0/` … `tests/phase10/`, plus `scripts/smoke/phaseN.sh`.
