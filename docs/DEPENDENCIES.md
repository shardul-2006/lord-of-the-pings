# RAG-Shield Dependencies

Exact installed versions of every Python package are pinned in `requirements.lock`
(`pip freeze`). Every model and dataset the code can use is listed in
`src/rag_shield/manifest.py`; `tests/phase10/test_dependencies_manifest.py` checks that each
appears below with a version or revision and a licence.

## Environment (v0.1 development machine)
| Item | Value |
|---|---|
| Interpreter | CPython 3.13.15 (64-bit, MSC v.1944) |
| Platform | Windows-11-10.0.26200-SP0, AMD Ryzen 7 260, 15 GB RAM, NVIDIA RTX 5060 Laptop (8 GB) |
| Shell | Git Bash (verify scripts), PowerShell |

## Python packages (direct dependencies)
| Package | Version (lock) | Purpose | Licence |
|---|---|---|---|
| numpy | 2.5.5 | Vector math | BSD-3-Clause |
| PyYAML | 6.0.3 | Policy files | MIT |
| pdfplumber | 0.11.10 | PDF layout: per-character font, colour, coordinates | MIT |
| PyMuPDF | 2.1 | Page render for the evidence overlay | AGPL-3.0 (commercial licence needed for closed distribution) |
| pypdf | 7.1.1 | PDF guard probe, encrypted-PDF fixture | BSD-3-Clause |
| reportlab | 5.1.0 | Fixture and synthetic PDF generation | BSD-3-Clause |
| markdown-it-py | 4.3.0 | Declared; Markdown is parsed with regexes over raw text (exact offsets) | MIT |
| beautifulsoup4 | 4.15.0 | Declared; HTML is parsed with stdlib `html.parser` (exact offsets) | MIT |
| scikit-learn (+ joblib 1.6.0) | 1.9.1 | TF-IDF, LinearSVC, logistic regression | BSD-3-Clause |
| pytest, ruff (dev) | 9.2.0, 0.17.5 | Tests, lint | MIT |
| fastapi, httpx, python-multipart (dev) | 0.165.0, 0.28.1, 0.0.34 | REST API and TestClient | MIT / BSD-3-Clause / Apache-2.0 |
| streamlit (dev) | 1.67.0 | Demo UI | Apache-2.0 |
| pydantic (dev pin < 2.12) | 2.11.9 | FastAPI models; newer pydantic-core wheels were blocked by Windows Smart App Control | MIT |

## Models
| Model | Use | Version / revision | Licence | Status |
|---|---|---|---|---|
| mock-llm-v1 | Deterministic LLM test double | in-repo | n/a (project code) | Used by all tests and the evaluation |
| llama3.1:8b | Real LLM via Ollama 0.40.8 for manual / demo runs | Ollama digest 46e0c10c039e (recorded in every trace as `llama3.1:8b@<digest>`) | Llama 3.1 Community License | Chosen in Phase 8; local GPU, no API key |
| protectai/deberta-v3-base-prompt-injection-v2 | Optional deep guard (`RAG_SHIELD_GUARD=deberta`) | HF commit 90c9989b1a342275dd0d1a95aad283c04e075671 | Apache-2.0 | Optional; not installed by default (needs transformers, torch) |
| BAAI/bge-small-en-v1.5 | Optional real embedder | HF commit 5c38ec7c405ec4b44b94cc5a9bb96e735b38267a | MIT | Optional; not installed by default (needs sentence-transformers) |
| tfidf-svm-platt-v1 | Fast first-pass classifier | trained in memory from seed-v1, seed 42 | n/a (project code) | Default |
| rule-guard-v1 | Default guard (no deep model) | in-repo | n/a (project code) | Default |
| hash-embedder-v1-d256 | Deterministic embedder | in-repo | n/a (project code) | Default |

## Datasets
| Dataset | Use | Version | Licence | Status |
|---|---|---|---|---|
| seed-v1 | Classifier train/dev/test, split by template (`data/train/seed.jsonl`) | seed 42 | synthetic, project | Used |
| synthetic-resumes-v2 | Phase 7 evaluation (25 clean, 25 poisoned, 10 trigger-word) | seed 42 | synthetic, project | Used |
| synthetic-sentiment-v1 | Dataset Gate demo (1,000 rows, planted poison) | seed 42 | synthetic, project | Used |
| NotInject | Optional benign FPR subset (`data/public/notinject/`) | pin when added | verify before use | Not used; never downloaded by the code |
| PromptShield | Optional public benchmark subset | pin when added | verify before use | Not used; never downloaded by the code |
| llmail-inject | Optional public benchmark | pin when added | verify before use | Not used; never downloaded by the code |
