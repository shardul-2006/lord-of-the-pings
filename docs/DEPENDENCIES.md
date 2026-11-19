# RAG-Shield Dependencies

> Skeleton (Phase 0). Exact installed versions are pinned in `requirements.lock`.
> Every model and dataset used by the code must be listed here with a revision/version and a
> licence before Phase 10.

## Environment
| Item | Value |
|---|---|
| Interpreter | CPython 3.13 (development machine) |
| Platform | Windows 11, CPU only |

## Python packages (core)
| Package | Purpose | Licence |
|---|---|---|
| numpy | Vector math | BSD-3-Clause |
| pyyaml | Policy files | MIT |
| pdfplumber | PDF layout (per-char font, colour, coordinates) | MIT |
| pymupdf | Page render for overlay | AGPL-3.0 (verify suitability before release) |
| pypdf | Encrypted-PDF fixture | BSD-3-Clause |
| reportlab | Fixture PDF generation | BSD-3-Clause |
| markdown-it-py | Static Markdown parsing | MIT |
| beautifulsoup4 | Static HTML parsing | MIT |
| scikit-learn | TF-IDF + Linear SVM | BSD-3-Clause |
| pytest, ruff (dev) | Tests, lint | MIT |

## Models
| Model | Use | Revision | Licence | Status |
|---|---|---|---|---|
| MockLLM (`mock-llm-v1`) | Test double | in-repo | n/a | Used by tests |
| Real LLM | Optional manual runs | _to pin_ | _to verify_ | **Open decision:** GPT-4o-mini (API) vs Llama-3.1-8B (Ollama) |
| protectai/deberta-v3-base-prompt-injection-v2 | Layer 2 deep guard (opt-in) | _to pin via RAG_SHIELD_GUARD_REVISION_ | Apache-2.0 (verify on model card) | Optional; refuses to load unpinned |
| tfidf-svm-platt-v1 | Layer 2 fast classifier | trained from seed-v1 (seed 42) | in-repo | Default |
| BAAI/bge-small-en-v1.5 | Real embeddings | _to pin_ | _to verify_ | Optional |

## Datasets
| Dataset | Use | Version | Licence | Status |
|---|---|---|---|---|
| seed-v1 (`data/train/seed.jsonl`) | Classifier train/dev/test, split by template | generated, seed 42 | in-repo | Phase 3 |
| Synthetic resumes / dataset | Fixtures, eval | generated, seeded | in-repo | Phases 1, 7, 9 |
| NotInject | Benign FPR | _to pin_ | _to verify_ | Optional, Phase 7 |
| PromptShield | Public benchmark | _to pin_ | _to verify_ | Optional, Phase 7 |
| llmail-inject | Public benchmark | _to pin_ | _to verify_ | Optional |
