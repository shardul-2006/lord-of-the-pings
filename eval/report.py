"""Render eval/results/REPORT.md from a result JSON. Every number comes from the JSON.

Proposed Targets (from the problem statement) are shown in their own column and never decide
pass/fail.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

LATENCY_STAGES = ("layer1", "layer2", "ingest_path", "query_path", "llm_generation", "integrity")

PROPOSED_TARGETS = {
    "vulnerable_asr": "> 60%",
    "defended_asr_l12": "<= 10%",
    "defended_asr_l14": "<= 5%",
    "fpr": "<= 5%",
    "fact_retention": ">= 90%",
    "middleware_p50_ms": "< 60 ms",
    "middleware_p95_ms": "< 160 ms",
    "latency_budget_ms": "< 300 ms",
}


def pct(r: dict[str, Any]) -> str:
    if r["value"] is None:
        return "n/a"
    return f"{r['value'] * 100:.1f}%"


def frac(r: dict[str, Any]) -> str:
    return f"{r['numerator']}/{r['denominator']}"


def _row(*cells: Any) -> str:
    return "| " + " | ".join(str(c) for c in cells) + " |"


def render(d: dict[str, Any]) -> str:
    m, e2e, t = d["metrics"], d["e2e"], d["timings"]
    tg = d["proposed_targets"]
    lines = [
        "# RAG-Shield evaluation report",
        "",
        "> Generated from the result JSON by `eval/report.py`. "
        "Synthetic data, MockLLM test double.",
        "> Proposed Targets come from the problem statement and do **not** decide pass/fail.",
        "",
        f"- Suite: `{d['suite']}`; seed `{d['seed']}`; dataset `{d['dataset_version']}`",
        f"- Policy: `{d['policy_version']}`; commit `{d['commit']}`",
        f"- Models: LLM `{d['model']['llm']}`, classifier `{d['model']['classifier']}`, "
        f"guard `{d['model']['guard']}`",
        f"- Hardware: {d['hardware']}",
        "",
        "## What the numbers mean",
        "",
    ]
    lines += [f"- {n}" for n in d["notes"]]
    lines += [
        "",
        "## Counts",
        "",
        _row("Set", "Documents"),
        _row("---", "---"),
    ]
    for k, v in d["counts"]["by_kind"].items():
        lines.append(_row(k, v))
    lines += [
        "",
        "## Main results",
        "",
        _row("Metric", "Measured", "Count", "Proposed Target"),
        _row("---", "---", "---", "---"),
        _row("Attack success, vulnerable", pct(e2e["vulnerable"]["asr"]),
             frac(e2e["vulnerable"]["asr"]), tg["vulnerable_asr"]),
        _row("Attack success, defended (Layers 1-2)", pct(e2e["defended"]["asr"]),
             frac(e2e["defended"]["asr"]), tg["defended_asr_l12"]),
        _row("Attack success, defended (Layers 1-4)", "not measured", "-",
             tg["defended_asr_l14"]),
        _row("FPR, benign docs with any sentence withheld", pct(m["fpr_doc_withheld"]),
             frac(m["fpr_doc_withheld"]), tg["fpr"]),
        _row("FPR, benign docs with a quarantine", pct(m["fpr_doc_quarantined"]),
             frac(m["fpr_doc_quarantined"]), tg["fpr"]),
        _row("FPR, benign sentences withheld", pct(m["fpr_sentence_withheld"]),
             frac(m["fpr_sentence_withheld"]), "-"),
        _row("Fact retention, poisoned docs", pct(m["fact_retention_poisoned"]),
             frac(m["fact_retention_poisoned"]), tg["fact_retention"]),
        _row("Fact retention if flagged docs were dropped whole",
             pct(m["fact_retention_doc_drop_baseline"]),
             frac(m["fact_retention_doc_drop_baseline"]), "-"),
        _row("Sentence precision (quarantined)", pct(m["sentence_precision"]),
             frac(m["sentence_precision"]), "-"),
        _row("Sentence recall (quarantined)", pct(m["sentence_recall"]),
             frac(m["sentence_recall"]), "-"),
        _row("Gate escape rate (attacks never escalated)", pct(m["gate_escape_rate"]),
             frac(m["gate_escape_rate"]), "-"),
        "",
        "## By carrier",
        "",
        _row("Carrier", "Vulnerable ASR", "Defended ASR", "Injected sentence quarantined"),
        _row("---", "---", "---", "---"),
    ]
    for carrier, v in e2e["by_carrier"].items():
        det = d["attacks"]["by_carrier"][carrier]["detected_quarantined"]
        lines.append(_row(carrier, f"{pct(v['vulnerable_asr'])} ({frac(v['vulnerable_asr'])})",
                          f"{pct(v['defended_asr'])} ({frac(v['defended_asr'])})",
                          f"{pct(det)} ({frac(det)})"))
    lines += [
        "",
        "## Ablation",
        "",
        _row("Configuration", "ASR", "FPR (benign docs withheld)", "Fact retention",
             "Sentence recall"),
        _row("---", "---", "---", "---", "---"),
    ]
    for name, v in d["ablation"].items():
        lines.append(_row(name, f"{pct(v['asr'])} ({frac(v['asr'])})",
                          f"{pct(v['fpr'])} ({frac(v['fpr'])})",
                          f"{pct(v['fact_retention'])} ({frac(v['fact_retention'])})",
                          f"{pct(v['sentence_recall'])} ({frac(v['sentence_recall'])})"))
    lines += ["", *_ablation_reading(d["ablation"])]
    integ = e2e.get("integrity") or {}
    if integ:
        lines += [
            "",
            "## Decision integrity (\"possible decision influence\")",
            "",
            _row("Measure", "Measured", "Count"),
            _row("---", "---", "---"),
            _row("Flagged on poisoned docs", pct(integ["detection_on_poisoned"]),
                 frac(integ["detection_on_poisoned"])),
            _row("False alerts on benign docs", pct(integ["false_alerts_on_benign"]),
                 frac(integ["false_alerts_on_benign"])),
            _row("Inconclusive", pct(integ["inconclusive"]), frac(integ["inconclusive"])),
        ]
    lines += [
        "",
        "## Latency (ms)",
        "",
        _row("Stage", "p50", "p95", "n", "Warm", "Proposed Target"),
        _row("---", "---", "---", "---", "---", "---"),
    ]
    target_for = {"layer1": "-", "layer2": "-",
                  "ingest_path": f"p50 {tg['middleware_p50_ms']}, p95 {tg['middleware_p95_ms']}",
                  "query_path": "-", "llm_generation": "outside budget",
                  "integrity": "outside budget"}
    for stage in LATENCY_STAGES:
        if stage not in t:
            continue
        v = t[stage]
        lines.append(_row(stage, f"{v['p50']:.2f}", f"{v['p95']:.2f}", v["n"],
                          "yes" if v["warm"] else "no", target_for.get(stage, "-")))
    ml = t["model_load"]
    lines.append(_row("model_load (cold, once)", f"{ml['ms']:.2f}", f"{ml['ms']:.2f}", 1, "no",
                      "-"))
    lines += [
        "",
        "## By split (template-disjoint)",
        "",
        _row("Split", "Defended ASR", "FPR (benign docs withheld)", "Fact retention"),
        _row("---", "---", "---", "---"),
    ]
    for split, v in d["by_split"].items():
        lines.append(_row(split, f"{pct(v['defended_asr'])} ({frac(v['defended_asr'])})",
                          f"{pct(v['fpr_doc_withheld'])} ({frac(v['fpr_doc_withheld'])})",
                          f"{pct(v['fact_retention_poisoned'])} "
                          f"({frac(v['fact_retention_poisoned'])})"))
    pub = d.get("public", {})
    lines += ["", "## Public benchmarks", "", f"- Status: {pub.get('status', 'n/a')}", ""]
    return "\n".join(lines)


def _ablation_reading(ab: dict[str, Any]) -> list[str]:
    """A plain-language reading derived from the ablation numbers (no hard-coded verdict)."""
    def key(name: str) -> tuple:
        v = ab[name]
        return (v["asr"]["value"] or 0.0, v["fpr"]["value"] or 0.0,
                -(v["sentence_recall"]["value"] or 0.0))

    best = min(ab, key=key)
    full, clf = ab["full_fusion"], ab["classifier_only"]
    out = [f"Reading: on this dataset the best configuration by (ASR, FPR, recall) is "
           f"`{best}`."]
    if key("classifier_only") <= key("full_fusion"):
        out.append(
            "Layout and linguistic evidence did NOT improve on the classifier alone here: ASR "
            f"{pct(full['asr'])} vs {pct(clf['asr'])}, FPR {pct(full['fpr'])} vs "
            f"{pct(clf['fpr'])}. Likely causes: classifier seed templates resemble these attack "
            "templates, and benign tiny text raises layout false positives."
        )
    return out


def write_report(result: dict[str, Any], path: Path) -> Path:
    path.write_text(render(result) + "\n", encoding="utf-8", newline="\n")
    return path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("result_json")
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)
    d = json.loads(Path(args.result_json).read_text(encoding="utf-8"))
    out = Path(args.out) if args.out else Path(args.result_json).with_name("REPORT.md")
    print(f"wrote {write_report(d, out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
