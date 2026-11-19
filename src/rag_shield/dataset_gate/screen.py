"""Dataset Gate: screen a text dataset (CSV or JSONL) before indexing or fine-tuning.

Per row: Layer 1 (Unicode canonicalization + signals) and Layer 2 (directive scoring) through
the same code as documents. Across rows: exact/near duplicates and trigger tokens.
Outputs in out_dir: screened.jsonl, quarantined.jsonl (reversible), report.json.
No row is ever deleted: len(screened) + len(quarantined) == len(input).
"""

from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rag_shield.dataset_gate.report import build_report, sha256_file, write_json
from rag_shield.dataset_gate.stats import exact_duplicates, near_duplicates, trigger_tokens
from rag_shield.layer1.ingest import ingest_text
from rag_shield.layer2 import screen
from rag_shield.layer2.classifier import default_classifier
from rag_shield.layer2.guard import Guard, RuleGuard
from rag_shield.models import DatasetReport, ScanStatus
from rag_shield.policy import load_policy
from rag_shield.scanner_guard import GuardConfig, ScanTimeout, run_with_timeout

SCREENED, QUARANTINED, REPORT = "screened.jsonl", "quarantined.jsonl", "report.json"


class DatasetFormatError(ValueError):
    pass


def read_samples(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    raw = path.read_bytes().decode("utf-8-sig")
    if path.suffix.lower() == ".jsonl":
        rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    elif path.suffix.lower() == ".csv":
        rows = list(csv.DictReader(io.StringIO(raw)))
    else:
        raise DatasetFormatError(f"unsupported dataset format {path.suffix!r} (csv or jsonl)")
    out = []
    for n, r in enumerate(rows, start=1):
        if not isinstance(r, dict) or "text" not in r:
            raise DatasetFormatError(f"row {n} has no 'text' field")
        out.append({**r, "id": str(r.get("id") or f"row{n:06d}"), "text": str(r["text"]),
                    "label": str(r.get("label", "")), "source": str(r.get("source", ""))})
    if len({r["id"] for r in out}) != len(out):
        raise DatasetFormatError("row ids are not unique")
    return out


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def screen_dataset(path: str | Path, out_dir: str | Path, policy: dict[str, Any] | None = None,
                   guard: Guard | None = None) -> DatasetReport:
    pol = load_policy(overrides=policy) if policy else load_policy()
    cfg = pol["dataset_gate"]
    out = Path(out_dir)
    limits = GuardConfig.from_env()

    def blocked(status: str, reason: str) -> DatasetReport:
        # fail closed: nothing is written, nothing counts as screened
        return DatasetReport(total=0, screened=0, quarantined=0, status=status, reason=reason,
                             out_dir=str(out))

    try:
        size = Path(path).stat().st_size
        if size == 0:
            return blocked("unsupported", "empty dataset file")
        if size > limits.max_bytes:
            return blocked("unsupported", f"oversize ({size} > {limits.max_bytes} bytes)")
        rows = read_samples(path)
        if not rows:
            return blocked("unsupported", "dataset has no rows")
    except (OSError, ValueError, UnicodeDecodeError) as e:
        return blocked("scan_failed", f"{type(e).__name__}: {e}")
    guard = guard or RuleGuard(policy=pol)
    try:  # analysis runs under a time budget and writes nothing until it has finished
        flags, exact, near, triggers, trig_stats = run_with_timeout(
            lambda: _analyse(rows, pol, guard),
            float(os.environ.get("RAG_SHIELD_DATASET_TIMEOUT") or cfg["timeout_s"]))
    except ScanTimeout as e:
        return blocked("scan_failed", f"timeout: {e}")
    except Exception as e:
        return blocked("scan_failed", f"analysis error: {type(e).__name__}: {e}")
    out.mkdir(parents=True, exist_ok=True)
    return _write_outputs(path, out, rows, flags, exact, near, triggers, trig_stats, pol, guard)


def _analyse(rows: list[dict[str, Any]], pol: dict[str, Any], guard: Guard) -> tuple:
    cfg = pol["dataset_gate"]
    flags: dict[str, list[dict[str, Any]]] = {}

    def flag(rid: str, name: str, reason: str) -> None:
        flags.setdefault(rid, []).append({"flag": name, "reason": reason})

    # Layers 1-2 per row
    for r in rows:
        scr = screen(ingest_text(r["text"], doc_id=f"row-{r['id']}"), pol, guard=guard)
        if scr.status in (ScanStatus.UNSUPPORTED, ScanStatus.SCAN_FAILED):
            flag(r["id"], "scan_failed", scr.reason)
        elif scr.status == ScanStatus.FLAGGED:
            flag(r["id"], "injected_directive",
                 "; ".join(q.decision_reason for q in scr.quarantine if q.status == "quarantined"))
        elif scr.status == ScanStatus.REVIEW_REQUIRED and cfg["quarantine_review_required"]:
            flag(r["id"], "review_required",
                 "; ".join(q.decision_reason for q in scr.quarantine))

    ids, texts = [r["id"] for r in rows], [r["text"] for r in rows]
    exact = exact_duplicates(ids, texts)
    for d in exact:
        flag(d["id"], "exact_duplicate", f"exact duplicate of {d['duplicate_of']}")
    exact_pairs = {frozenset((d["id"], d["duplicate_of"])) for d in exact}
    near = [p for p in near_duplicates(ids, texts, cfg["near_duplicate_threshold"])
            if frozenset((p["a"], p["b"])) not in exact_pairs]
    for p in near:
        flag(p["b"], "near_duplicate", f"near duplicate of {p['a']} (cosine {p['cosine']})")
    triggers, trig_stats = trigger_tokens(ids, texts, [r["label"] for r in rows], cfg["trigger"])
    trig_set = set(triggers)
    for r in rows:
        hit = sorted(trig_set & {t for t in triggers if t in r["text"].lower()})
        if hit:
            flag(r["id"], "trigger_token",
                 f"contains rare label-correlated token(s) {', '.join(hit)}")
    return flags, exact, near, triggers, trig_stats


def _write_outputs(path: str | Path, out: Path, rows: list[dict[str, Any]],
                   flags: dict[str, list[dict[str, Any]]], exact: list, near: list,
                   triggers: list[str], trig_stats: list, pol: dict[str, Any],
                   guard: Guard) -> DatasetReport:
    quarantining = {"scan_failed", "injected_directive", "review_required", "exact_duplicate",
                    "trigger_token"}
    quarantined = {rid for rid, f in flags.items() if any(x["flag"] in quarantining for x in f)}
    q_rows = [{**r, "_gate": {"flags": flags[r["id"]], "quarantined_at":
                              datetime.now(timezone.utc).isoformat()}}
              for r in rows if r["id"] in quarantined]
    _write_jsonl(out / SCREENED, [r for r in rows if r["id"] not in quarantined])
    _write_jsonl(out / QUARANTINED, q_rows)
    report = build_report(
        input_path=str(path), input_sha256=sha256_file(path), rows=rows, flags=flags,
        quarantined=quarantined, trigger_stats=trig_stats, near_dups=near,
        policy_version=pol["version"],
        model_versions={"classifier": default_classifier().version, "guard": guard.model_id},
    )
    write_json(out / REPORT, report)
    return DatasetReport(
        total=len(rows), screened=len(rows) - len(quarantined), quarantined=len(quarantined),
        duplicates=len(exact), trigger_tokens=triggers, report_path=str(out / REPORT),
        near_duplicates=len(near), flags_by_reason=report["summary"]["flags_by_reason"],
        out_dir=str(out),
    )


def release_sample(out_dir: str | Path, sample_id: str, reviewer: str) -> dict[str, Any]:
    """Move a quarantined row back to screened.jsonl (original order) and log who/when."""
    if not reviewer:
        return {"released": False, "reason": "a reviewer name is required"}
    out = Path(out_dir)
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    quarantined = _read_jsonl(out / QUARANTINED)
    match = [r for r in quarantined if r["id"] == sample_id]
    if not match:
        return {"released": False, "reason": f"{sample_id} is not quarantined"}
    row = {k: v for k, v in match[0].items() if k != "_gate"}
    order = {rid: i for i, rid in enumerate(report["order"])}
    screened = sorted(_read_jsonl(out / SCREENED) + [row], key=lambda r: order[r["id"]])
    _write_jsonl(out / SCREENED, screened)
    _write_jsonl(out / QUARANTINED, [r for r in quarantined if r["id"] != sample_id])
    event = {"action": "release", "id": sample_id, "by": reviewer,
             "at": datetime.now(timezone.utc).isoformat()}
    report["events"].append(event)
    for s in report["samples"]:
        if s["id"] == sample_id:
            s["status"] = "released"
    report["summary"]["quarantined"] -= 1
    report["summary"]["screened"] += 1
    write_json(out / REPORT, report)
    return {"released": True, "event": event, "screened": len(screened),
            "quarantined": len(quarantined) - 1}
