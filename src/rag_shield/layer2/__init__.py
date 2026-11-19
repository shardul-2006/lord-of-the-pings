"""Layer 2: sentence scoring, routing, fusion and reversible quarantine (Spec E).

screen(ingest) -> ScreenResult. Final document status:
  flagged          at least one sentence quarantined (only that sentence is withheld)
  review_required  at least one ambiguous sentence (held from the high-stakes path)
  clean            nothing withheld
  unsupported / scan_failed  passed through from Layer 1, or the guard failed/timed out;
                   no screened chunks are produced, so nothing reaches defended retrieval.
"""

from __future__ import annotations

from typing import Any

from rag_shield import timing
from rag_shield.layer2 import linguistic
from rag_shield.layer2.classifier import default_classifier
from rag_shield.layer2.fusion import CLEAN, fuse
from rag_shield.layer2.guard import Guard, make_guard
from rag_shield.layer2.quarantine import build_chunks, doc_status, now
from rag_shield.layer2.routing import SentenceFeatures, group_for_routing, route
from rag_shield.layer2.sentences import split_sentences
from rag_shield.models import (
    Finding,
    IngestResult,
    QuarantineRecord,
    ScanStatus,
    ScreenResult,
    Sentence,
    Signal,
)
from rag_shield.policy import load_policy
from rag_shield.scanner_guard import ScanTimeout, run_with_timeout

BLOCKED = (ScanStatus.UNSUPPORTED, ScanStatus.SCAN_FAILED)


def _overlaps(sig: Signal, s: Sentence) -> bool:
    off = sig.detail.get("canonical_offsets")
    if not off:
        return bool(set(sig.source_span_ids) & set(s.source_span_ids))
    c0, c1 = off
    a, b = s.canonical_offsets
    if c0 == c1:  # insertion point (e.g. stripped Unicode Tag payload)
        return a <= c0 <= b
    return c0 < b and c1 > a


def _features(
    sentences: list[Sentence], signals: list[Signal], clf: Any, policy: dict[str, Any]
) -> tuple[list[SentenceFeatures], dict[str, list[Signal]]]:
    weights = policy["fusion"]["signal_weights"]
    carriers = set(policy["fusion"]["carrier_signals"])
    per_sentence = {s.sentence_id: [g for g in signals if _overlaps(g, s)] for s in sentences}

    texts: list[list[str]] = []
    for s in sentences:
        payloads = [g.detail["decoded"] for g in per_sentence[s.sentence_id]
                    if g.detail.get("decoded")]
        texts.append([s.text, *payloads])
    flat = [t for group in texts for t in group]
    probs = list(clf.predict_proba(flat)) if flat else []

    feats, k = [], 0
    for s, group in zip(sentences, texts, strict=True):
        p = [float(x) for x in probs[k:k + len(group)]]
        k += len(group)
        ling = [linguistic.score_text(t) for t in group]
        sigs = per_sentence[s.sentence_id]
        hiding_types = sorted({g.type for g in sigs if g.type in weights})
        feats.append(SentenceFeatures(
            sentence_id=s.sentence_id,
            text=s.text,
            classifier=max(p),
            linguistic=max(r.score for r in ling),
            cues=sorted({c for r in ling for c in r.cues}),
            hiding=max((weights[t] for t in hiding_types), default=0.0),
            hiding_types=hiding_types,
            carrier_types=sorted({g.type for g in sigs if g.type in carriers}),
            payloads=group[1:],
        ))
    return feats, per_sentence


def screen(
    ingest: IngestResult,
    policy: dict[str, Any] | None = None,
    *,
    classifier: Any = None,
    guard: Guard | None = None,
) -> ScreenResult:
    policy = load_policy(overrides=policy) if policy else load_policy()
    version = policy["version"]
    doc = ingest.document
    if ingest.status in BLOCKED:
        return ScreenResult(doc, ingest.status, policy_version=version, reason=ingest.reason)
    prov = ingest.provenance
    if prov is None:
        return ScreenResult(doc, ScanStatus.SCAN_FAILED, policy_version=version,
                            reason="no provenance map: ingest result is incomplete")

    with timing.stage("layer2"):
        return _screen(ingest, policy, classifier or default_classifier(),
                       guard or make_guard(policy["guard"]["kind"]))


def _signal_edges(ingest: IngestResult, types: set[str]) -> list[int]:
    """Outer edges of signalled text, used as sentence boundaries.

    Adjacent signalled ranges separated only by whitespace are merged first, so hidden text
    wrapped over several lines stays one sentence. Zero-length insertion points (stripped
    Unicode) sit inside words and are not boundaries.
    """
    text = ingest.canonical_text
    ranges = sorted(
        tuple(g.detail["canonical_offsets"]) for g in ingest.signals
        if g.type in types and "canonical_offsets" in g.detail
        and g.detail["canonical_offsets"][0] != g.detail["canonical_offsets"][1]
    )
    merged: list[list[int]] = []
    for a, b in ranges:
        if merged and (a <= merged[-1][1] or not text[merged[-1][1]:a].strip()):
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [o for r in merged for o in r]


def _screen(ingest: IngestResult, policy: dict[str, Any], clf: Any, guard: Guard) -> ScreenResult:
    doc, version = ingest.document, policy["version"]
    max_chars = int(policy["chunk_max_chars"])
    fusion = policy["fusion"]
    flagged_types = set(fusion["signal_weights"]) | set(fusion["carrier_signals"])
    edges = _signal_edges(ingest, flagged_types)

    with timing.stage("sentences"):
        sentences = split_sentences(ingest.canonical_text, doc.doc_id, edges, ingest.provenance)
    with timing.stage("cheap_checks"):
        feats, per_sentence = _features(sentences, ingest.signals, clf, policy)

    routing_log, escalated = [], []
    for i, members in enumerate(group_for_routing(feats, max_chars), start=1):
        routed = route(f"{doc.doc_id[:12]}-r{i}", [feats[j] for j in members], policy)
        routing_log.append(routed.log)
        if routed.route == "escalate":
            escalated.extend(members)

    guard_scores: dict[int, float] = {}
    if escalated:
        texts, owners, contexts = [], [], []
        for j in escalated:
            neighbours = " ".join(feats[n].text for n in (j - 1, j + 1) if 0 <= n < len(feats))
            for t in [feats[j].text, *feats[j].payloads]:
                texts.append(t)
                owners.append(j)
                contexts.append(neighbours)
        try:
            with timing.stage("guard"):
                scores = run_with_timeout(lambda: guard.score(texts, contexts),
                                          float(policy["guard"]["timeout_s"]))
        except ScanTimeout as e:
            return ScreenResult(doc, ScanStatus.SCAN_FAILED, sentences=sentences,
                                routing_log=routing_log, policy_version=version,
                                reason=f"guard timeout: {e}")
        except Exception as e:  # any guard error fails closed
            return ScreenResult(doc, ScanStatus.SCAN_FAILED, sentences=sentences,
                                routing_log=routing_log, policy_version=version,
                                reason=f"guard error: {type(e).__name__}: {e}")
        for j, sc in zip(owners, scores, strict=True):
            guard_scores[j] = max(guard_scores.get(j, 0.0), float(sc))

    findings, records = [], []
    clf_version = getattr(clf, "version", type(clf).__name__)
    for j, (s, f) in enumerate(zip(sentences, feats, strict=True)):
        semantic = guard_scores.get(j, f.classifier)
        fused = fuse(semantic, f.linguistic, f.hiding, bool(f.carrier_types), policy,
                     f.hiding_types, f.cues)
        sigs = per_sentence[s.sentence_id]
        if fused.disposition != CLEAN or sigs:
            findings.append(Finding(
                sentence_id=s.sentence_id,
                signals=sigs,
                model_versions={
                    "classifier": clf_version,
                    "guard": guard.model_id if j in guard_scores else "not_escalated",
                    "linguistic": linguistic.VERSION,
                },
                score=fused.score,
                policy_version=version,
            ))
        if fused.disposition != CLEAN:
            records.append(QuarantineRecord(
                s.sentence_id, fused.disposition, fused.reason, None, {"created_at": now()}
            ))

    withheld = {r.sentence_id for r in records}
    return ScreenResult(
        document=doc,
        status=doc_status(records),
        sentences=sentences,
        findings=findings,
        quarantine=records,
        screened_chunks=build_chunks(sentences, withheld, doc.doc_id, max_chars),
        routing_log=routing_log,
        policy_version=version,
        reason="layer2 complete",
    )


def screen_report(result: ScreenResult) -> dict[str, Any]:
    """JSON view used by the CLI: statuses, withheld sentences with evidence, screened text."""
    text = {s.sentence_id: s.text for s in result.sentences}
    spans = {s.sentence_id: s.source_span_ids for s in result.sentences}
    finding = {f.sentence_id: f for f in result.findings}

    def item(r: QuarantineRecord) -> dict[str, Any]:
        f = finding.get(r.sentence_id)
        return {
            "sentence_id": r.sentence_id,
            "text": text.get(r.sentence_id, ""),
            "status": r.status,
            "score": f.score if f else None,
            "signals": sorted({g.type for g in f.signals}) if f else [],
            "reason": r.decision_reason,
            "source_span_ids": spans.get(r.sentence_id, []),
        }

    return {
        "status": result.status.value,
        "reason": result.reason,
        "policy_version": result.policy_version,
        "document": result.document.to_dict(),
        "quarantined": [item(r) for r in result.quarantine if r.status == "quarantined"],
        "review_required": [item(r) for r in result.quarantine if r.status == "review_required"],
        "screened_text": result.screened_text,
        "screened_chunks": [c.to_dict() for c in result.screened_chunks],
        "routing_log": result.routing_log,
        "findings": [f.to_dict() for f in result.findings],
        "events": result.events,
    }
