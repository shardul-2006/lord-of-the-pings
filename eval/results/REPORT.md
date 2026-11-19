# RAG-Shield evaluation report

> Generated from the result JSON by `eval/report.py`. Synthetic data, MockLLM test double.
> Proposed Targets come from the problem statement and do **not** decide pass/fail.

- Suite: `all`; seed `42`; dataset `synthetic-resumes-v2-seed42 (25fe2277ea112b1b)`
- Policy: `policy_v1 (tier external_upload)`; commit `0d64e1344a686cfb637e1ccddfea7acc836e7ed4-dirty`
- Models: LLM `mock-llm-v1`, classifier `tfidf-svm-platt-v1/seed-v1-aee7bcede87d-seed42`, guard `rule-guard-v1 (no deep model)`
- Hardware: Windows 11 | AMD64 | AMD64 Family 25 Model 117 Stepping 2, AuthenticAMD | python 3.13.15

## What the numbers mean

- Synthetic data only: 25 clean + 25 poisoned + 10 benign trigger-word resumes. These are small samples; read the counts, not just the percentages.
- LLM is MockLLM, a string-matching test double. 'Attack success' therefore means the payload reached the model context intact; it says nothing about how a real LLM behaves.
- Layer 3 spotlighting is not measured here: datamarking breaks MockLLM's string match and would show a fake improvement. A real LLM is required.
- No component was fitted on these resumes (classifier: seed-v1; thresholds: policy_v1), so metrics use all documents; per-split rows are shown for completeness. The classifier seed templates and these attack templates share an author, which may inflate results.
- The vulnerable branch reads plain pdfplumber text; it does not read PDF metadata, so metadata attacks cannot succeed there.
- Guard: rule-guard-v1 (no deep model).

## Counts

| Set | Documents |
| --- | --- |
| clean | 25 |
| poisoned | 25 |
| benign_trigger | 10 |

## Main results

| Metric | Measured | Count | Proposed Target |
| --- | --- | --- | --- |
| Attack success, vulnerable | 80.0% | 20/25 | > 60% |
| Attack success, defended (Layers 1-2) | 0.0% | 0/25 | <= 10% |
| Attack success, defended (Layers 1-4) | not measured | - | <= 5% |
| FPR, benign docs with any sentence withheld | 11.4% | 4/35 | <= 5% |
| FPR, benign docs with a quarantine | 0.0% | 0/35 | <= 5% |
| FPR, benign sentences withheld | 1.7% | 4/234 | - |
| Fact retention, poisoned docs | 100.0% | 100/100 | >= 90% |
| Fact retention if flagged docs were dropped whole | 0.0% | 0/100 | - |
| Sentence precision (quarantined) | 100.0% | 23/23 | - |
| Sentence recall (quarantined) | 92.0% | 23/25 | - |
| Gate escape rate (attacks never escalated) | 0.0% | 0/25 | - |

## By carrier

| Carrier | Vulnerable ASR | Defended ASR | Injected sentence quarantined |
| --- | --- | --- | --- |
| low_contrast | 100.0% (5/5) | 0.0% (0/5) | 100.0% (5/5) |
| metadata | 0.0% (0/5) | 0.0% (0/5) | 100.0% (5/5) |
| off_page | 100.0% (5/5) | 0.0% (0/5) | 100.0% (5/5) |
| tiny_font | 100.0% (5/5) | 0.0% (0/5) | 100.0% (5/5) |
| visible | 100.0% (5/5) | 0.0% (0/5) | 60.0% (3/5) |

## Ablation

| Configuration | ASR | FPR (benign docs withheld) | Fact retention | Sentence recall |
| --- | --- | --- | --- | --- |
| classifier_only | 0.0% (0/25) | 0.0% (0/35) | 100.0% (100/100) | 100.0% (25/25) |
| layout_plus_classifier | 0.0% (0/25) | 8.6% (3/35) | 100.0% (100/100) | 76.0% (19/25) |
| full_fusion | 0.0% (0/25) | 11.4% (4/35) | 100.0% (100/100) | 92.0% (23/25) |

Reading: on this dataset the best configuration by (ASR, FPR, recall) is `classifier_only`.
Layout and linguistic evidence did NOT improve on the classifier alone here: ASR 0.0% vs 0.0%, FPR 11.4% vs 0.0%. Likely causes: classifier seed templates resemble these attack templates, and benign tiny text raises layout false positives.

## Decision integrity ("possible decision influence")

| Measure | Measured | Count |
| --- | --- | --- |
| Flagged on poisoned docs | 100.0% | 25/25 |
| False alerts on benign docs | 0.0% | 0/35 |
| Inconclusive | 0.0% | 0/60 |

## Latency (ms)

| Stage | p50 | p95 | n | Warm | Proposed Target |
| --- | --- | --- | --- | --- | --- |
| layer1 | 10.20 | 14.14 | 60 | yes | - |
| layer2 | 4.38 | 5.70 | 60 | yes | - |
| ingest_path | 15.74 | 19.85 | 60 | yes | p50 < 60 ms, p95 < 160 ms |
| query_path | 0.07 | 0.13 | 120 | yes | - |
| llm_generation | 0.02 | 0.04 | 120 | yes | outside budget |
| integrity | 0.24 | 0.38 | 29 | yes | outside budget |
| model_load (cold, once) | 36.04 | 36.04 | 1 | no | - |

## By split (template-disjoint)

| Split | Defended ASR | FPR (benign docs withheld) | Fact retention |
| --- | --- | --- | --- |
| train | 0.0% (0/15) | 9.5% (2/21) | 100.0% (60/60) |
| dev | 0.0% (0/5) | 14.3% (1/7) | 100.0% (20/20) |
| test | 0.0% (0/5) | 14.3% (1/7) | 100.0% (20/20) |

## Public benchmarks

- Status: not present

