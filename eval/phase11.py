"""Phase 11 (optional breadth) runner: multilingual, second domain, adaptive evasion, backdoor.

    python -m eval.phase11                  # MockLLM; writes eval/results/<ts>_phase11.json
    python -m eval.phase11 --llm real       # also judges evasion answers with the real LLM
    python -m eval.phase11 --report <json>  # re-render PHASE11.md from a saved result

PHASE11.md is generated from the result JSON only; every ratio is numerator/denominator.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eval.backdoor import run_backdoor
from eval.evasion import run_evasion
from eval.harness import git_commit, hardware
from eval.multilingual import run_multilingual
from scripts.make_paper_fixtures import FIXTURES as PAPER_FIXTURES
from scripts.make_paper_fixtures import main as make_paper_fixtures

RESULTS = Path(__file__).resolve().parent / "results"
PARTS = ("multilingual", "adapter", "evasion", "backdoor")


def run_adapter(llm: Any = None) -> dict[str, Any]:
    """Each paper fixture under the hr and paper_review adapters: same engine, config only."""
    from rag_shield.rag.compare import compare
    from rag_shield.rag.llm import MOCK_PAPER_OUTPUT, MockLLM
    from rag_shield.shield import Shield

    llm = llm or MockLLM()
    rows = []
    with tempfile.TemporaryDirectory() as td:
        make_paper_fixtures(["--out", td])
        for name in PAPER_FIXTURES:
            path = Path(td) / f"{name}.pdf"
            for domain in ("hr", "paper_review"):
                shield = Shield(domain, db_path=":memory:", keep_forensic=False, home=td)
                try:
                    res = shield.ingest(path).to_dict()
                finally:
                    shield.close()
                traces = compare(path, llm, defense="shield", domain=domain)
                rows.append({
                    "fixture": name, "domain": domain, "status": res["status"],
                    "quarantined": len(res["quarantined_ids"]),
                    "review_required": len(res["review_ids"]),
                    "vulnerable_output": traces["vulnerable"].output[:120],
                    "defended_output": traces["defended"].output[:120],
                    "defended_compromised": MOCK_PAPER_OUTPUT in traces["defended"].output,
                })
    return {"llm": llm.model_id, "rows": rows}


def run_phase11(llm_kind: str = "mock", parts: tuple[str, ...] = PARTS) -> dict[str, Any]:
    from rag_shield.rag.llm import get_llm

    real = get_llm("real") if llm_kind == "real" else None
    out: dict[str, Any] = {
        "phase": 11, "created": datetime.now(timezone.utc).isoformat(),
        "commit": git_commit(), "hardware": hardware(), "llm": llm_kind,
    }
    if "multilingual" in parts:
        out["multilingual"] = run_multilingual()
    if "adapter" in parts:
        out["adapter"] = run_adapter()
    if "evasion" in parts:
        out["evasion"] = run_evasion(real)
    if "backdoor" in parts:
        out["backdoor"] = run_backdoor()
    return out


# ---------------------------------------------------------------------------------- report
def frac(r: dict[str, Any]) -> str:
    return f"{r['numerator']}/{r['denominator']}"


def _row(*cells: Any) -> str:
    return "| " + " | ".join(str(c) for c in cells) + " |"


def render(d: dict[str, Any]) -> str:
    L = ["# RAG-Shield Phase 11: optional breadth", "",
         f"Generated from the result JSON. Commit `{d['commit']}`, {d['created']}. "
         f"Hardware: {d['hardware']}.", "",
         "All data is synthetic. MockLLM is a deterministic test double; with MockLLM, attack "
         "success means the payload reached the model's context.", ""]
    if "multilingual" in d:
        m = d["multilingual"]
        L += ["## 1. Multilingual payloads", "",
              f"Dataset `{m['dataset_version']}`: injections and benign resume lines in "
              "Hinglish, Hindi script and Telugu script. Cues were written on the dev split; "
              "the test split was written first and the cues were not changed after the first "
              "test run. The same author wrote both, and no native speaker has reviewed them, "
              "so treat this as a smoke test.", "",
              "Held-out **test** split, visible text (no hiding signal):", "",
              _row("Language", "Cue set", "Detected (withheld)", "Detected (quarantined)",
                   "FPR (withheld)", "FPR (quarantined)"),
              _row(*["---"] * 6)]
        for cs, res in m["cue_sets"].items():
            for lang in m["languages"]:
                g = res["visible"][lang]["test"]
                L.append(_row(lang, cs, frac(g["detected_withheld"]),
                              frac(g["detected_quarantined"]), frac(g["fpr_withheld"]),
                              frac(g["fpr_quarantined"])))
        L += ["", "Held-out test split, hidden in a `display:none` element:", "",
              _row("Cue set", "Detected (withheld)", "Detected (quarantined)", "FPR (withheld)",
                   "FPR (quarantined)"), _row(*["---"] * 5)]
        for cs, res in m["cue_sets"].items():
            g = res["hidden"]["all_test"]
            L.append(_row(cs, frac(g["detected_withheld"]), frac(g["detected_quarantined"]),
                          frac(g["fpr_withheld"]), frac(g["fpr_quarantined"])))
        L += ["", "Missed test injections (multilingual cues, visible): "
              + ("; ".join(f"`{t}`" for t in m["misses"]) or "none") + ".",
              "False positives on test benign lines: "
              + ("; ".join(f"`{t}`" for t in m["false_positives"]) or "none") + ".", ""]
    if "adapter" in d:
        a = d["adapter"]
        L += ["## 2. Second domain: paper review", "",
              "`src/rag_shield/adapters/paper_review.py` is configuration only: trusted "
              "sources mapped to trust tiers, sensitive actions, thresholds (quarantine 0.65, "
              "review 0.35), five extra linguistic cues, and the integrity task and rubric. "
              "The engine is the same. "
              f"Defended answers come from `{a['llm']}`.", "",
              _row("Fixture", "Domain", "Status", "Quarantined", "Review", "Defended answer "
                   "compromised"), _row(*["---"] * 6)]
        for r in a["rows"]:
            L.append(_row(r["fixture"], r["domain"], r["status"], r["quarantined"],
                          r["review_required"], "yes" if r["defended_compromised"] else "no"))
        L += ["", "Reading: a visible \"give a positive review only\" request carries no hiding "
              "signal and no HR cue, so the HR configuration lets it through; the paper_review "
              "configuration quarantines it. A benign paper that QUOTES an injection string "
              "has that quote quarantined in both domains (a false positive, sentence-level "
              "only; the reviewer can release it).", ""]
    if "evasion" in d:
        e = d["evasion"]
        s = e["summary"]
        L += ["## 3. Adaptive evasion", "",
              f"Generator `{e['generator_version']}`: {e['variants']} variants of `"
              f"{e['base_payload']}` (split, paraphrased, obfuscated) in {e['documents']} "
              "documents. Homoglyph variants have no hidden-PDF carrier (standard PDF fonts "
              "cannot encode Cyrillic).", "",
              _row("Family / carrier", "n", "Vulnerable ASR", "Defended ASR",
                   "Defended: any fragment reached"), _row(*["---"] * 5)]
        for k, g in [("all", s["all"]), *s["by_family_carrier"].items()]:
            L.append(_row(k, g["n"], frac(g["vulnerable_asr"]), frac(g["defended_asr"]),
                          frac(g["defended_any_fragment"])))
        if "llm" in s:
            L += ["", f"Real LLM `{e['llm_model']}` on the visible_md and hidden_pdf carriers "
                  "(regex judge; `mentioned` is an upper bound, `recommended` excludes "
                  "sentences with refusal or suspicion words):", "",
                  _row("Branch", "CEO mentioned", "CEO recommended"), _row(*["---"] * 3)]
            for branch, g in s["llm"].items():
                L.append(_row(branch, frac(g["ceo_mentioned"]), frac(g["ceo_recommended"])))
        L += ["", "Defended escapes: " + (", ".join(f"`{x}`" for x in s["defended_escapes"])
                                         or "none") + ".", "",
              "Reading: hidden-PDF text is withheld on the layout signal alone, whatever the "
              "wording. Visible paraphrases avoid the cue patterns and the TF-IDF classifier, "
              "and homoglyph, letter-spaced and leetspeak text is not folded back to plain "
              "letters, so these reach the context when there is no strong hiding signal.", ""]
    if "backdoor" in d:
        b = d["backdoor"]
        L += ["## 4. Backdoor demo", "",
              f"Dataset `{b['dataset_version']}` (seed {b['seed']}), trigger `{b['trigger']}`. "
              f"Held-out test: {b['test']['per_class']} positive and {b['test']['per_class']} "
              "negative new reviews (seed "
              f"{b['test']['seed']}); backdoor success = triggered positive reviews predicted "
              "negative. Models are sklearn defaults, fixed in advance.", "",
              _row("Poison rows", "Gate: trigger rows removed", "Gate: clean rows removed",
                   "Model", "Backdoor before Gate", "Backdoor after Gate",
                   "Clean accuracy before / after"), _row(*["---"] * 7)]
        for one in b["sweep"]:
            if one.get("status") != "completed":
                L.append(_row(one["poison_rows"], one.get("status"), "", "", "", "", ""))
                continue
            g = one["gate"]
            for model, r in one["models"].items():
                L.append(_row(f"{one['poison_rows']} ({frac(one['poison_rate'])})",
                              frac(g["trigger_rows_removed"]), frac(g["clean_rows_removed"]),
                              model, frac(r["before_gate"]["backdoor_success"]),
                              frac(r["after_gate"]["backdoor_success"]),
                              f"{frac(r['before_gate']['clean_accuracy'])} / "
                              f"{frac(r['after_gate']['clean_accuracy'])}"))
        L += ["", "Reading:", *_backdoor_reading(b), ""]
    return "\n".join(L).rstrip() + "\n"


def _backdoor_reading(b: dict[str, Any]) -> list[str]:
    out = []
    for one in b["sweep"]:
        if one.get("status") != "completed":
            continue
        n, g = one["poison_rows"], one["gate"]
        learned = {m: r for m, r in one["models"].items()
                   if r["before_gate"]["backdoor_success"]["numerator"] > 0}
        gate = (f"the Gate flagged the trigger and removed {frac(g['trigger_rows_removed'])} "
                "poison rows" if g["trigger_tokens"] else
                "the Gate did NOT flag the trigger (it is no longer rare: doc frequency above "
                "`max_doc_freq`), so no poison rows were removed")
        if not learned:
            out.append(f"- {n} poison rows: no model learned the backdoor; {gate}.")
        else:
            eff = ", ".join(f"{m} {frac(r['before_gate']['backdoor_success'])} -> "
                            f"{frac(r['after_gate']['backdoor_success'])}"
                            for m, r in learned.items())
            out.append(f"- {n} poison rows: backdoor learned ({eff}, before -> after); {gate}.")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--llm", choices=["mock", "real"], default="mock")
    p.add_argument("--parts", default=",".join(PARTS), help="comma list of " + ",".join(PARTS))
    p.add_argument("--report", default=None, help="only re-render PHASE11.md from this JSON")
    p.add_argument("--out", default=str(RESULTS))
    args = p.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.report:
        d = json.loads(Path(args.report).read_text(encoding="utf-8"))
    else:
        parts = tuple(x for x in args.parts.split(",") if x)
        d = run_phase11(args.llm, parts)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = out / f"{stamp}_phase11.json"
        path.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {path}")
    (out / "PHASE11.md").write_text(render(d), encoding="utf-8", newline="\n")
    print(f"wrote {out / 'PHASE11.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
