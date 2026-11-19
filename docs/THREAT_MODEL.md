# RAG-Shield Threat Model

| Dimension | Definition |
|---|---|
| Attacker controls | Content of externally supplied PDF, Markdown and static HTML, including metadata and layout |
| Defender controls | System/developer instructions, evaluation criteria, model config, retrieval policy, security config |
| Entry points | Pre-index ingestion; retrieved chunks at query time |
| Objective | Make the LLM follow document-borne instructions instead of treating the document as evidence |
| Protected assets | Decision integrity, authorized outputs, legitimate document facts, audit trail, secrets where applicable |
| Success test | A documented, attack-directed deviation in the end-to-end output or decision |
| Non-goals | Preventing every prompt injection; image/OCR carriers (no OCR); universal training-data backdoor detection |

## Attack classes

**Baseline:**
- Visible directives in the document body.
- Tiny-font, low-contrast and off-page PDF text.
- Metadata, HTML and Markdown carriers (properties, hidden comments, alt-text).
- Unicode concealment (Tag characters, bidi controls, zero-width runs).
- Benign trigger-word negatives (e.g. "system override module"), which must **not** be flagged.

**Extended:**
- Split or paraphrased directives.
- Hinglish, Hindi-script and Telugu-script payloads.
- Adaptive evasion.
- Canary-leak and exfiltration output attacks (image beacons, untrusted links).
- Dataset poisoning (rare trigger tokens tied to a flipped label, injected directives, duplicates).

## Benchmark case requirements

Every benchmark case must state:
1. **Attacker control:** which part of the input the attacker wrote.
2. **Entry point:** ingestion or query-time retrieval.
3. **Expected malicious behaviour:** what a successful attack makes the system do.
4. **Scoring:** how success is decided (the rubric), with numerator and denominator reported.

## Fail-closed principle

A scan that is unsupported, incomplete or errors out is reported as `unsupported` or
`scan_failed`. Such documents are **blocked** from defended retrieval and never labelled `clean`.
