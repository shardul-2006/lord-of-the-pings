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

## Layer 2 (Phase 3)
Pipeline: sentences -> cheap checks (linguistic cues + calibrated SVM, also run on decoded hidden
payloads) -> routing -> guard on escalated chunks -> fusion -> disposition -> screened chunks.

- **Sentences** split on `. ! ? । ॥`, at line breaks unless the next line starts lowercase, and at
  the edges of hiding/carrier signals (zero-length Unicode insertion points excepted).
- **Routing** groups sentences into chunks that never mix suspicious and clean text. A chunk
  passes only if clearly clean with no hiding or carrier signal; every decision is logged.
- **Fusion** `score = 0.45*S + 0.35*L + 0.40*H + 0.20*C*max(S,L)`; hard rule: strong hiding +
  directive syntax is quarantined. >= 0.70 quarantined, >= 0.40 review_required (policy_v1.yaml).
  Hidden text without a directive therefore lands in review_required, not quarantine.
- **Guard.** Default `RuleGuard` is *not* a deep model (rules + classifier); its model id says
  so. `DebertaGuard` is opt-in (`RAG_SHIELD_GUARD=deberta`) and requires a pinned revision.
  Guard error or timeout -> the whole document is `scan_failed` with no screened chunks.
- **Classifier** is trained in memory from the deterministic seed set (`seed-v1`), split by
  template; Platt calibration uses dev only. Seed-set accuracy is not a performance claim.
- **Quarantine** is reversible: release/requarantine change record status, rebuild screened
  chunks and append an audit event (who, when, policy version). Nothing is deleted.

## Stores and index boundaries (Phase 4)
| Store | Where | Used as LLM context? |
|---|---|---|
| Forensic | `$RAG_SHIELD_HOME/forensic/<sha256>.<ext>`, read-only copy of the original bytes | Never (overlay rendering and audit only) |
| Processing | ledger tables `source_spans`, `sentences` | No |
| Trust ledger | `documents`, `findings` (with highlight boxes), `quarantine`, `events` | No |
| Defended index | `index_chunks` + `index_state.index_version`; screened chunks only | Yes (defended branch) |
| Vulnerable demo | separate in-memory namespace inside `compare` | Yes (vulnerable branch only) |

- **Index sync.** Release, re-quarantine and rescan run in ONE SQLite transaction: update the
  quarantine row, delete the document's chunk rows, rebuild them from permitted sentences, bump
  `index_version`, log the event, commit. Any failure rolls back everything, so a released
  sentence becomes retrievable only after authorization **and** sync both succeed.
- **Vector-store cache.** The in-memory store is rebuilt from `index_chunks` whenever the
  committed `index_version` differs from the loaded one, so separate processes (CLI calls, API
  workers) stay consistent. Rebuild is a full reload, which is fine at demo scale.
- **Fail closed.** `unsupported`/`scan_failed` documents get zero index rows; a failed rescan
  deletes the document's previous rows. `Shield.filter()` drops any chunk whose id or text is
  not in the current index.
- **Overlay** renders the forensic original with PyMuPDF; boxes come from the provenance map in
  pdfplumber coordinates (same as PyMuPDF for unrotated pages). Tiny boxes are padded to 6 pt;
  off-page text is marked with a band on the nearest page edge. Rotated pages are not handled.
