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

## Hardening (Phase 10)
- **Network blocked for the whole suite.** `tests/conftest.py` patches `socket` at session start:
  any non-loopback connection or DNS lookup raises `NetworkBlockedError` (loopback stays open
  because asyncio on Windows uses a local socket pair). `test_no_network_in_tests.py` proves the
  block is active, so every passing test ran offline.
- **Fail-closed audit** (`test_fail_closed_everywhere.py`): malformed, encrypted, oversize,
  timeout and empty inputs through the CLI (`shield-run`), the REST API (`/ingest`), the
  Streamlit upload path (`app/uploads.py`) and the Dataset Gate (library, CLI, `/dataset`, UI).
  None is ever `clean`; documents get zero index rows; datasets produce no `screened.jsonl`.
- **Limits** are configurable by environment: `RAG_SHIELD_MAX_BYTES`, `RAG_SHIELD_MAX_PAGES`,
  `RAG_SHIELD_SCAN_TIMEOUT`, `RAG_SHIELD_DATASET_TIMEOUT`.
- **Dependencies**: `src/rag_shield/manifest.py` lists every model/dataset the code can use;
  a test requires each to appear in `docs/DEPENDENCIES.md` with a version and licence, and the
  optional Hugging Face models are pinned to immutable commits in code.
- **Clean install**: `bash scripts/clean_install_test.sh` builds a fresh venv constrained by
  `requirements.lock` and runs `verify_phase.sh 10`.

## Optional breadth (Phase 11)
`python -m eval.phase11` writes `eval/results/<ts>_phase11.json` and `PHASE11.md` (rendered from
the JSON only; every ratio is numerator/denominator).
- **Multilingual** (`multilingual-v1`): dev split used to write the cues; the test split was
  written first and the cues were frozen before the first test run. English-only vs
  multilingual cue sets; visible and hidden (`display:none`) carriers.
- **Paper-review adapter**: each paper fixture under `hr` and `paper_review`; a test asserts the
  adapter module contains no functions or classes (configuration only).
- **Adaptive evasion** (`evasion-v1`): deterministic split / paraphrase / obfuscation variants
  over Markdown, hidden HTML and hidden PDF carriers. Success = every payload fragment reaches
  the context (MockLLM convention). `--llm real` also judges real answers with a regex
  (`mentioned` upper bound, `recommended` excludes refusal words); outputs are saved.
- **Backdoor**: TF-IDF logistic regression and naive Bayes (sklearn defaults, fixed in advance)
  trained before and after Dataset Gate filtering; held-out reviews from a different seed.
  The poison rate is swept (10, 30, 50, 100 rows of 1,000) because 1% did not implant a backdoor.
