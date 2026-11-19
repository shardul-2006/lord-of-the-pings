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

## Layer 1 (Phase 2)
Pipeline: `scanner_guard.check_file` -> private temp copy -> parse (time-limited) ->
`unicode_clean.clean_text` -> `ProvenanceMap` -> signals with canonical offsets.

- **Coordinates.** `SourceSpan.source_offsets` are character offsets in the original file for
  Markdown/HTML, and offsets in the extraction stream for PDF. `ProvenanceMap` maps any
  canonical range to per-span source pieces (one-to-many and many-to-one) and to one highlight
  bbox per span, at word precision for PDFs.
- **PDF spans.** Words are grouped into lines, and lines into runs of identical style; each run
  is a span. Hidden text stays in the text and is tagged, never deleted.
- **low_contrast assumption.** The background is white unless a filled rectangle lies under the
  word's centre. Images and gradients behind text are not considered. Threshold: WCAG contrast
  ratio < 1.5.
- **Metadata / alt-text** are *carrier* signals: their text is appended as its own spans so
  Layer 2 can score it, but they alone do not make a document suspicious.
- **HTML** is parsed with the stdlib `html.parser` (what BeautifulSoup wraps) because it gives
  exact source positions for every text node and entity; `<script>/<style>` text is dropped.
- **Ingest status.** `unsupported`/`scan_failed` on guard or parser failure; `review_required`
  when any hiding signal exists; otherwise `clean`. Layer 2 sets the final disposition.
- **Timeouts** run the parser in a worker thread and abandon it; CPU and memory are not hard
  limited (Python cannot kill a thread).

## Index boundaries
_TODO (Phase 4)_: forensic store, processing store, defended index, vulnerable demo index;
index_version bump on quarantine/release/rescan before content is exposed.
