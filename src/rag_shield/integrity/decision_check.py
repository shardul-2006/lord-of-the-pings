"""Decision-integrity check (Spec H): does a suspicious passage change the decision?

For each suspicious passage (and all of them together) the SAME task, rubric and prompt
structure run WITH and WITHOUT the passage, `runs` times each, in an isolated path: the LLM's
tools are disabled for the whole check. A benign-removal control measures how much removing
ordinary sentences moves the score, so dropping a real qualification is not mistaken for
manipulation. An alert needs |delta| >= threshold AND |delta| > the largest control swing.

Results are always labelled "possible decision influence": this is evidence of sensitivity
to the passage, not proof of an attack. Temperature 0 helps repeatability, not determinism.
"""

from __future__ import annotations

import json
import re
import statistics
import time
from pathlib import Path
from typing import Any

from rag_shield import timing
from rag_shield.models import IngestResult, IntegrityResult, ScanStatus, ScreenResult, Sentence
from rag_shield.policy import load_policy
from rag_shield.rag.llm import CONTEXT_BEGIN, CONTEXT_END, SCORE_FORMAT_MARKER, LLMClient

LABEL = "possible decision influence"
PROMPT = (
    "You are scoring a job candidate. Task: {task}\n"
    "{rubric}\n"
    f"{SCORE_FORMAT_MARKER}\n"
    f"{CONTEXT_BEGIN}\n{{context}}\n{CONTEXT_END}\n"
    "JSON:"
)


class ScoreParseError(ValueError):
    pass


def _screen_doc(doc: Any) -> ScreenResult | None:
    if isinstance(doc, ScreenResult):
        return doc
    from rag_shield.layer1.ingest import ingest
    from rag_shield.layer2 import screen

    if isinstance(doc, IngestResult):
        return screen(doc)
    if isinstance(doc, (str, Path)):
        return screen(ingest(doc))
    return None


def suspicious_ids(scr: ScreenResult, hiding_types: set[str]) -> list[str]:
    """Withheld sentences plus sentences carrying a HIDING signal. Carrier signals (ordinary
    metadata, alt-text) alone do not make a sentence suspicious."""
    withheld = {r.sentence_id for r in scr.quarantine if r.status in
                ("quarantined", "review_required")}
    hidden = {f.sentence_id for f in scr.findings
              if any(g.type in hiding_types for g in f.signals)}
    order = [s.sentence_id for s in scr.sentences]
    return [sid for sid in order if sid in withheld | hidden]


def parse_score(raw: str) -> dict[str, Any]:
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        raise ScoreParseError(f"no JSON object in output: {raw[:80]!r}")
    try:
        obj = json.loads(m.group(0))
        score = float(obj["score"])
    except (ValueError, KeyError, TypeError) as e:
        raise ScoreParseError(f"bad score JSON: {e}") from e
    if not 0 <= score <= 100:
        raise ScoreParseError(f"score out of range: {score}")
    return {"score": score, "verdict": str(obj.get("verdict", "")),
            "supporting_evidence_ids": list(obj.get("supporting_evidence_ids", []))}


def _context(sentences: list[Sentence], drop: set[str]) -> str:
    return "\n".join(f"[{s.sentence_id}] {s.text}" for s in sentences if s.sentence_id not in drop)


def _runs(llm: LLMClient, task: str, rubric: str, sentences: list[Sentence], drop: set[str],
          n: int) -> list[dict[str, Any]]:
    prompt = PROMPT.format(task=task, rubric=rubric, context=_context(sentences, drop))
    return [parse_score(llm.generate(prompt)) for _ in range(n)]


def _stats(runs: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [r["score"] for r in runs]
    return {
        "scores": scores,
        "mean": statistics.fmean(scores),
        "stdev": statistics.pstdev(scores) if len(scores) > 1 else 0.0,
        "spread": max(scores) - min(scores),
        "verdicts": [r["verdict"] for r in runs],
    }


def check(
    task: str,
    doc: Any,
    llm: LLMClient,
    *,
    passages: list[str] | None = None,
    threshold: float | None = None,
    runs: int | None = None,
    controls: bool = True,
    policy: dict[str, Any] | None = None,
) -> IntegrityResult:
    """`doc`: path, IngestResult or ScreenResult. `passages`: sentence ids (or exact sentence
    texts) to test; default = Layer 2's suspicious sentences."""
    pol = load_policy(overrides=policy) if policy else load_policy()
    cfg = pol["integrity"]
    threshold = float(cfg["threshold"] if threshold is None else threshold)
    n = int(cfg["runs"] if runs is None else runs)
    base = IntegrityResult(False, 0.0, threshold, task=task,
                           model={"id": llm.model_id, "settings": dict(llm.settings)})

    with timing.stage("integrity_screen"):
        scr = _screen_doc(doc)
    if scr is None or scr.status in (ScanStatus.UNSUPPORTED, ScanStatus.SCAN_FAILED):
        base.status, base.reason = "inconclusive", "document could not be screened"
        return base

    sentences = scr.sentences
    by_text = {s.text: s.sentence_id for s in sentences}
    hiding = set(pol["fusion"]["signal_weights"])
    ids = ([by_text.get(p, p) for p in passages] if passages is not None
           else suspicious_ids(scr, hiding))
    ids = [i for i in ids if i in {s.sentence_id for s in sentences}]
    if not ids:
        base.reason = "no suspicious passages to test"
        return base

    previous_tools = llm.tools_enabled
    llm.tools_enabled = False  # isolated path: the check can never take real actions
    start = time.perf_counter()
    try:
        with timing.stage("integrity"):
            result = _compare(task, cfg["rubric"], llm, sentences, ids, n, threshold,
                              controls, int(cfg["max_controls"]), base)
    except ScoreParseError as e:
        base.status, base.reason = "inconclusive", f"unparseable model output: {e}"
        result = base
    finally:
        llm.tools_enabled = previous_tools
    result.timings = {"integrity_ms": (time.perf_counter() - start) * 1000.0}
    result.tools_enabled_during_check = False
    return result


def _compare(task: str, rubric: str, llm: LLMClient, sentences: list[Sentence], ids: list[str],
             n: int, threshold: float, controls: bool, max_controls: int,
             res: IntegrityResult) -> IntegrityResult:
    text = {s.sentence_id: s.text for s in sentences}
    with_all = _stats(_runs(llm, task, rubric, sentences, set(), n))

    groups = [[i] for i in ids] + ([ids] if len(ids) > 1 else [])
    passages = []
    for group in groups:
        without = _stats(_runs(llm, task, rubric, sentences, set(group), n))
        passages.append({
            "removed_sentence_ids": group,
            "removed_text": [text[i] for i in group],  # the exact evidence difference
            "with": with_all,
            "without": without,
            "delta": with_all["mean"] - without["mean"],
        })
    top = max(passages, key=lambda p: abs(p["delta"]))

    control: dict[str, Any] = {"enabled": controls, "passages": [], "max_abs_delta": 0.0}
    if controls:
        # baseline = document without the suspicious text; remove one ordinary sentence at a time
        baseline = _stats(_runs(llm, task, rubric, sentences, set(ids), n))
        benign = [s.sentence_id for s in sentences if s.sentence_id not in ids][:max_controls]
        for sid in benign:
            without = _stats(_runs(llm, task, rubric, sentences, set(ids) | {sid}, n))
            d = baseline["mean"] - without["mean"]
            control["passages"].append({"removed_sentence_id": sid, "removed_text": text[sid],
                                        "delta": d})
        control["max_abs_delta"] = max((abs(c["delta"]) for c in control["passages"]),
                                       default=0.0)

    material = abs(top["delta"]) >= threshold
    beyond_control = abs(top["delta"]) > control["max_abs_delta"]
    res.possible_decision_influence = bool(material and beyond_control)
    res.delta = top["delta"]
    res.runs_with = top["with"]["scores"]
    res.runs_without = top["without"]["scores"]
    res.removed_sentence_ids = top["removed_sentence_ids"]
    res.passages = passages
    res.control = control
    res.variance = {
        "runs_per_condition": n,
        "max_stdev": max(max(p["with"]["stdev"], p["without"]["stdev"]) for p in passages),
        "max_spread": max(max(p["with"]["spread"], p["without"]["spread"]) for p in passages),
    }
    res.reason = (
        f"|delta|={abs(top['delta']):.1f} vs threshold {threshold:g}; "
        f"largest benign-removal swing {control['max_abs_delta']:.1f}"
    )
    return res
