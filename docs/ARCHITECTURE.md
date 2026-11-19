# RAG-Shield Architecture

> Skeleton (Phase 0). Sections are filled in as phases land. See
> `RAG_SHIELD_PRODUCT_OVERVIEW.md` §4 for flowcharts.

## Data forms (never mixed)
- **Original:** immutable source bytes and native spans (forensic store).
- **Canonical:** normalized text with a map to one or more source spans (processing store).
- **Screened:** chunks approved for model use, always carrying provenance IDs (defended index).

## Modules
| Module | Responsibility | Phase |
|---|---|---|
| `models.py` | Data contracts (Spec B) | 0 |
| `timing.py` | Per-run stage timing | 0 |
| `rag/llm.py` | `LLMClient`, `MockLLM`, real client | 0 |
| `scanner_guard.py` | File-type, magic-byte, size/time limits; fail closed | 2 |
| `layer1/` | Canonicalization, hiding signals, provenance map | 2 |
| `layer2/` | Sentence scoring, routing, fusion, quarantine | 3 |
| `ledger/` | Trust ledger (SQLite), evidence overlay | 4 |
| `rag/` | Embedder, vector store, pipeline, traces, index sync | 1, 4 |
| `layer3/` | Spotlighting, trust tiers | 5 |
| `layer4/` | Canary, exfil stripping, grounding | 5 |
| `integrity/` | Decision-integrity check | 6 |
| `dataset_gate/` | Batch dataset screening | 9 |
| `shield.py` | Library facade | 0 (stub), 4 |

## Status values
`clean`, `flagged`, `review_required`, `unsupported`, `scan_failed`. The last two are blocked
from defended retrieval.

## Index boundaries
_TODO (Phase 4)_: forensic store, processing store, defended index, vulnerable demo index;
index_version bump on quarantine/release/rescan before content is exposed.
