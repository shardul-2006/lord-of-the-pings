# RAG-Shield v0.1

A security middleware that sits between documents and an LLM. It canonicalizes PDF, Markdown and
HTML while keeping a map back to the original page and position, scores every sentence from
layout, semantic and linguistic signals, quarantines only the risky sentence (reversibly),
records everything in a trust ledger with an evidence overlay, keeps quarantined text out of the
retrieval index, adds context isolation and output checks, checks whether a decision was
influenced, and screens datasets in batch. Scans that fail are never treated as clean.

Product overview: `docs/RAG_SHIELD_PRODUCT_OVERVIEW.md`. Build plan: `docs/RAG_SHIELD_CLAUDE_CODE_PLAN.md`.
Measured results: `eval/results/REPORT.md` (core) and `eval/results/PHASE11.md` (optional breadth:
multilingual, second domain, adaptive evasion, backdoor). Threat model: `docs/THREAT_MODEL.md`.

## Feature Verification Matrix & Capability Status

The following audit matrix delineates verified code implementation against operational limitations and empirical evaluation targets.

| Capability | Status | Implementation Area | Verified Behavior & Honest Limitations |
| :--- | :---: | :--- | :--- |
| **Sentence-Level Quarantine & Fact Retention** | **Working** | `src/rag_shield/layer2/screen.py`<br>`src/rag_shield/ledger/store.py`<br>`src/rag_shield/rag/pipeline.py` | **Verified:** Sentences evaluated individually using multi-vector fusion; high-risk sentences isolated in SQLite ledger, clean sentences indexed for defended retrieval.<br>**Limitation:** "100% Fact Retention" is an empirical target, not an invariant guarantee; sentence boundary splitting can truncate facts or allow instructions split across sentence boundaries to slip through. |
| **Cloud-Agnostic & Local-First Operation** | **Working** | `src/rag_shield/rag/llm.py`<br>`src/rag_shield/layer2/classifier.py`<br>`src/rag_shield/shield.py` | **Verified:** Fully functional with no external cloud services, API keys, or telemetry. Uses local scikit-learn SGDClassifier, offline SQLite ledger, local Ollama (`llama3.1:8b`), and deterministic `MockLLM`.<br>**Note:** Fast execution on standard CPU; optional DeBERTa model is CPU-intensive. |
| **PDF & HTML Layout Inspection** | **Working** | `src/rag_shield/layer1/pdf.py`<br>`src/rag_shield/layer1/markup.py` | **Verified:** PDF extracts exact font sizes, bounding boxes, background color contrast, and off-page coordinates. HTML detects inline `display:none`, `visibility:hidden`, `opacity:0`, `color:transparent`, negative off-screen coordinates, zero heights, and `aria-hidden`.<br>**Limitation:** HTML layout inspection uses static AST parsing (`HTMLParser`), not a browser engine; external CSS classes and complex stylesheets are not resolved. |
| **Bounding-Box Overlays & Trust Ledger** | **Working** | `src/rag_shield/layer3/overlay.py`<br>`src/rag_shield/ledger/store.py`<br>`app/streamlit_app.py` | **Verified:** Generates visual PNG overlays highlighting suspicious PDF regions with color-coded risk boxes (red/amber). Full provenance trail stored with SHA-256 hashes, risk signals, and analyst audit events.<br>**Limitation:** Visual bounding-box overlay is PDF-only (HTML displays structured sentence telemetry). Assumes unrotated pages and light background. |
| **Randomized Delimiter Spotlighting** | **Working** | `src/rag_shield/rag/spotlight.py`<br>`src/rag_shield/rag/pipeline.py` | **Verified:** Encloses untrusted context within cryptographically randomized hex tokens (`secrets.token_hex(8)`) and enforces data-boundary prompts.<br>**Limitation:** Spotlighting provides probabilistic prompt boundary isolation; it does not guarantee determinism against adversarial jailbreaks without classifier filtering. |
| **Counterfactual Decision Integrity Checks** | **Working** | `src/rag_shield/integrity/decision_check.py`<br>`src/rag_shield/adapters/` | **Verified:** Evaluates downstream decisions with and without suspicious passages across repeated trials with disabled tools. Uses benign-removal negative controls to avoid penalizing legitimate qualifications. Wired to domain adapters (`hr`, `paper_review`).<br>**Limitation:** Labels "possible decision influence", not definitive proof of malice. Requires multiple LLM calls. |
| **Dataset Gate Batch Screening** | **Working** | `src/rag_shield/dataset/gate.py`<br>`src/rag_shield/dataset/duplicates.py`<br>`app/uploads.py` | **Verified:** Screens pre-retrieval CSV/JSONL corpora for backdoor triggers (masked token disagreement correlation), exact SHA-256 duplicates, and MinHash/LSH near-duplicates. Exports `report.json`, `screened.jsonl` (clean), and `quarantined.jsonl` (poison).<br>**Limitation:** Backdoors without distinct trigger tokens, or triggers with high poison frequency (>10%), can evade rarity detection. |

## Quickstart (three commands)
```bash
python -m venv .venv && source .venv/Scripts/activate     # Linux/macOS: .venv/bin/activate
pip install -e ".[dev]"
bash scripts/verify_phase.sh 10                            # lint + all tests + smoke: PHASE 10: PASS
```
Then `bash scripts/demo.sh` for the guided demo, or `streamlit run app/streamlit_app.py`.

## Library
```python
from rag_shield import Shield

shield = Shield(domain="hr", source_tier="external_upload")
result = shield.ingest("resume.pdf")          # guard -> Layer 1 -> Layer 2 -> ledger -> index
print(result.status, result.alerts)           # clean / flagged / review_required / blocked
safe_chunks = shield.filter(retrieved_chunks) # keeps only chunks in the current defended index
check = shield.validate_output(answer, safe_chunks)   # canary, exfil links, grounding
shield.release(sentence_id, reviewer="alice") # reversible; index rebuilt before exposure
report = shield.screen_dataset("data.jsonl", "out/")  # Dataset Gate
```

## CLI
```bash
python scripts/make_fixtures.py                                   # sample documents
python -m rag_shield.cli ingest data/fixtures/tiny_font.pdf --json        # Layer 1 signals
python -m rag_shield.cli screen data/fixtures/smoke_poisoned.pdf --json   # Layers 1-2
python -m rag_shield.cli compare data/fixtures/smoke_poisoned.pdf --spotlight   # vulnerable vs defended
python -m rag_shield.cli shield-run data/fixtures/smoke_poisoned.pdf --json     # full pipeline + ledger
python -m rag_shield.cli review list --json
python -m rag_shield.cli review release <sentence_id> --reviewer alice
python -m rag_shield.cli overlay data/fixtures/smoke_poisoned.pdf --page 1 --out overlay.png
python -m rag_shield.cli integrity data/fixtures/smoke_poisoned.pdf --task "Score this candidate"
python scripts/make_paper_fixtures.py                             # second domain: paper review
python -m rag_shield.cli compare data/fixtures/paper_visible_directive.pdf --domain paper_review
python -m rag_shield.cli validate-output --answer-file data/fixtures/answer_bad.txt --chunks-file data/fixtures/chunks.json
python scripts/make_poisoned_dataset.py
python -m rag_shield.cli dataset-gate screen data/synthetic_dataset/poisoned.jsonl --out gate_out
python -m eval.harness --suite all --llm mock --seed 42          # evaluation + REPORT.md
python -m eval.phase11                                            # Phase 11 + PHASE11.md
```
Domains (`--domain`, or `Shield(domain=...)`): `hr` (default) and `paper_review`. An adapter in
`src/rag_shield/adapters/` is configuration only: trusted sources mapped to trust tiers,
sensitive actions, thresholds, extra linguistic cues, and the integrity task and rubric.
State (ledger, forensic originals) lives in `$RAG_SHIELD_HOME` (default `~/.rag_shield`).
Scan limits: `RAG_SHIELD_MAX_BYTES`, `RAG_SHIELD_MAX_PAGES`, `RAG_SHIELD_SCAN_TIMEOUT`.

## REST API & Modern React Console
```bash
pip install uvicorn
uvicorn app.api:create_app --factory --port 8000
```
- **React Web Console**: Open `http://localhost:8000/` for the modern React TypeScript SPA with drag-and-drop ingestion, selectable attack presets, visual evidence inspection, expandable sentence telemetry, arena comparison, review actions, and dataset screening.
- **REST API Routes**: `GET /health`, `GET /samples`, `POST /samples/{sample_name}/ingest`, `POST /ingest`, `POST /ask`, `GET /findings/{doc_id}`, `GET /review`, `POST /release/{sentence_id}`, `POST /requarantine/{sentence_id}`, `GET /overlay/{doc_id}/{page}`, `POST /integrity`, `POST /dataset`, `POST /demo-dataset/screen`.
- **Streamlit Console**: Available concurrently via `streamlit run app/streamlit_app.py` on port 8501.

## Real LLM (optional)
Tests always use the deterministic `MockLLM`. For a real model the prototype uses local
Llama 3.1 8B through Ollama (no API key; documents stay on the machine):
```bash
ollama pull llama3.1:8b
export RAG_SHIELD_LLM=ollama RAG_SHIELD_LLM_MODEL=llama3.1:8b
python -m rag_shield.cli compare data/fixtures/smoke_poisoned.pdf --llm real
```
OpenAI-compatible APIs also work (`RAG_SHIELD_LLM=openai`, `OPENAI_API_KEY`). In our first real
run Llama 3.1 8B did **not** follow the hidden instruction (0/3), so the demo shows the attack
with MockLLM. On the Phase 11 evasion set (56 documents, `PHASE11.md`) it never recommended the
candidate as CEO; 3/56 undefended and 2/56 defended answers adopted the payload's framing
(labelled by an AI reviewer, `eval/evasion_manual_review.json`; not yet human-checked).

## Honest limits
- Results come from small synthetic sets (25 + 25 resumes, 1,000 dataset rows) and a
  string-matching MockLLM. Read the counts in `eval/results/REPORT.md`, not just percentages.
- On our synthetic set the classifier alone matched full fusion; the layout signals did not
  lower attack success and added false positives from harmless tiny text (see the ablation).
- Aggressive thresholds can raise false positives on technical text; benign tiny footers and
  phrases like "system prompt templates" are held for review (FPR 4/35 documents withheld).
- An instruction split across many sentences can slip past sentence-level quarantine.
- Adaptive evasion (`PHASE11.md`): visible paraphrases of the payload passed 20/20, and
  homoglyph, letter-spaced and leetspeak text is not folded back to plain letters. Only text
  with a strong hiding signal (tiny or invisible PDF text) is withheld whatever its wording.
- Hindi, Hinglish and Telugu cues are translations of the English cue families, tested on a
  small hand-written set (24 held-out injections) with no native-speaker review.
- A paper that quotes an attack string has that quote quarantined (sentence only).
- Spotlighting reduces compliance probabilistically, not deterministically; it is not measured
  with MockLLM.
- Output filters are syntactic: they do not stop semantic covert channels.
- The default guard is rules + classifier; the DeBERTa guard is optional and slower on CPU.
- No public benchmark exists for PDF visual-layout attacks; public subsets are optional.
- The decision-integrity check costs extra LLM calls, is outside the latency budget, and reports
  "possible decision influence", never proof of attack. Payloads stripped in Layer 1 (Unicode
  Tag characters) cannot be tested by it.
- The Dataset Gate cannot guarantee a clean dataset: backdoors without an obvious trigger,
  paraphrased duplicates and spread-out poisoning can pass. At 10% poison the trigger is no
  longer rare, the Gate does not flag it, and the backdoor survives filtering (`PHASE11.md`).
- Failed or unsupported scans are blocked, which can reduce retrieval utility.
- The low-contrast check assumes a white page unless a filled rectangle is under the text; the
  overlay assumes unrotated pages. No OCR, no DOCX.
- Scan timeouts abandon the worker thread; CPU and memory are not hard-limited.
