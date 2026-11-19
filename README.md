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

## REST API
```bash
pip install uvicorn
uvicorn app.api:create_app --factory --port 8000
```
Routes: `GET /health`, `POST /ingest`, `POST /ask`, `GET /findings/{doc_id}`, `GET /review`,
`POST /release/{sentence_id}`, `POST /requarantine/{sentence_id}`, `GET /overlay/{doc_id}/{page}`,
`POST /integrity`, `POST /dataset`. Uploads are deleted after each request.

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
with MockLLM.

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
