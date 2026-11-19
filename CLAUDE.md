# Project: RAG-Shield
Security middleware for document RAG: canonicalize inputs, quarantine only malicious
sentences (reversibly), keep provenance, check whether a decision was influenced,
and screen datasets in batch mode.

## Rules
- Implement only the requested phase and its declared prerequisites.
- Read existing types/interfaces and tests before editing.
- Do not change scope. No OCR, no DOCX, no new features without approval.
- Never fabricate benchmark metrics or claim unrun tests passed.
- Do not silently swap LLMs, guard models, datasets, licences or scope.
- Preserve original source bytes; canonicalization must track source spans.
- Never delete content: quarantine is reversible and logged in the ledger.
- Hiding signals (tiny font, low contrast, off-page) are SIGNALS, not auto-deletion.
- Preserve a single ZWJ/ZWNJ (U+200D/U+200C) so Hindi and Telugu text is not damaged.
- Normal defended RAG consumes ONLY screened chunks.
- On quarantine/release/rescan, update the retrieval index before exposing content, or block.
- Scanner errors are errors, never "clean". Unsupported/failed scans never enter defended retrieval.
- Strong hiding/directive signals escalate to the deep model even if the fast model says clean.
- Record retrieved chunk IDs/order, prompts, model ID/revision, settings in every trace.
- The Phase 1 rule-based filter is an integration test, not a security benchmark.
- Tests use MockLLM and the hash embedder: deterministic, offline.
- Add integration tests when public contracts change.
- Record model versions, thresholds, seeds and code commit in result files.
- Synthetic or public data only. Never log personal content.
- Before finishing: run the phase verify command; report commands and results,
  files changed, and known limitations.

## Commands
- Install: pip install -e ".[dev]"
- Verify a phase: bash scripts/verify_phase.sh <N>
- Tests only: python -m pytest -q   (pip .exe launchers are blocked on this machine)
- Fixtures: python scripts/make_fixtures.py

## Local environment notes
- Windows + Git Bash. Activate the venv first: `source .venv/Scripts/activate`.
