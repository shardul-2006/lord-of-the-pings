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
| DeBERTa-v3 prompt-injection guard | Layer 2 deep model | _to pin_ | _to verify_ | Phase 3, optional real run |
| BAAI/bge-small-en-v1.5 | Real embeddings | _to pin_ | _to verify_ | Optional |

## Datasets
| Dataset | Use | Version | Licence | Status |
|---|---|---|---|---|
| Synthetic resumes / dataset | Fixtures, eval | generated, seeded | in-repo | Phases 1, 7, 9 |
| NotInject | Benign FPR | _to pin_ | _to verify_ | Optional, Phase 7 |
| PromptShield | Public benchmark | _to pin_ | _to verify_ | Optional, Phase 7 |
| llmail-inject | Public benchmark | _to pin_ | _to verify_ | Optional |
