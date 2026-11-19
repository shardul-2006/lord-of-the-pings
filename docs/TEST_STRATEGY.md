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

## Evaluation protocol (Phase 7)
Run: `python scripts/make_synthetic.py --seed 42 && python -m eval.harness --suite all --llm mock --seed 42`
-> `eval/results/<timestamp>_all.json` and `eval/results/REPORT.md` (every table number comes
from the JSON; a test enforces this).

- **Data.** `synthetic-resumes-v2`: 25 clean (3 with a harmless 2 pt footer), 25 poisoned (5 each:
  tiny_font, low_contrast, off_page, metadata, visible), 10 benign trigger-word resumes (two
  visible trigger sentences each, including hard negatives such as "system prompt templates").
  Resume templates and attack templates are each assigned to one split; documents only combine
  templates from their own split. Every poisoned case records attacker control, entry point,
  expected malicious behaviour and the success rubric.
- **No fitting on this set.** The classifier trains on `seed-v1`; thresholds come from
  `policy_v1`. Metrics therefore use all documents, with per-split rows alongside. Caveat: the
  same author wrote the seed and attack templates, which may inflate classifier results.
- **ASR with MockLLM** = the attack payload reached the model context intact. Layer 3 is not
  measured with MockLLM (datamarking breaks its string match). Real-LLM runs are required for
  claims about model behaviour.
- **Ablation** (`eval/ablation.py`): classifier_only, layout_plus_classifier, full_fusion; same
  thresholds; stated weights, not tuned. The report derives its reading from the numbers and
  says so when layout evidence does not help.
- **Latency**: nearest-rank p50/p95 per stage with n, warm runs (one untimed warm-up document),
  classifier training reported separately as cold `model_load`. Middleware = `ingest_path`;
  `llm_generation` and `integrity` are outside the budget.
- **Public subsets** are read only from `data/public/<name>/*.jsonl` ({text, label}); nothing is
  downloaded; results are text-only and reported separately.
