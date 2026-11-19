"""Per-document evaluation runs shared by the suites.

For each synthetic resume: Layer 1 + Layer 2 under a given policy, which sentences were
withheld, whether labelled facts survived, which routing entry carried the injected sentence,
and the defended / vulnerable answers from MockLLM.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rag_shield import timing
from rag_shield.layer1.ingest import ingest
from rag_shield.layer2 import screen
from rag_shield.layer2.guard import RuleGuard
from rag_shield.models import Chunk, ScreenResult
from rag_shield.rag.llm import LLMClient
from rag_shield.rag.pipeline import (
    DEFAULT_QUESTION,
    RagPipeline,
    chunk_id,
    extract_pdf_text,
    group_sentences,
    sentence_ids,
    sha256_file,
    split_sentences,
)
from scripts.make_synthetic import SUCCESS_MARKER

QUESTION = DEFAULT_QUESTION
BENIGN_KINDS = ("clean", "benign_trigger")


def _norm(text: str) -> str:
    """Collapse whitespace: wrapped PDF lines put newlines inside sentences and facts."""
    return " ".join(text.split())


def _is_injected(text: str, injected: str | None) -> bool:
    if not injected:
        return False
    t, inj = _norm(text), _norm(injected)
    return inj in t or (len(t) >= 10 and t in inj)


def defended_answer(scr: ScreenResult, llm: LLMClient) -> str:
    pipe = RagPipeline()
    pipe.build_index(scr.screened_chunks, "defended")
    return pipe.answer(QUESTION, "defended", llm).output


def vulnerable_answer(path: Path, llm: LLMClient) -> str:
    """Naive RAG: plain pdfplumber text, no screening (what the vulnerable branch sees)."""
    try:
        text = extract_pdf_text(path)
    except Exception:
        text = ""
    sha = sha256_file(path)
    sents = sentence_ids(sha, split_sentences(text))
    chunks = [Chunk(chunk_id(sha, i), sha, g.text)
              for i, g in enumerate(group_sentences(sents), start=1)]
    pipe = RagPipeline()
    pipe.build_index(chunks, "vulnerable")
    return pipe.answer(QUESTION, "vulnerable", llm).output


def run_doc(label: dict[str, Any], root: Path, policy: dict[str, Any], llm: LLMClient,
            *, with_vulnerable: bool = False) -> dict[str, Any]:
    path = root / label["file"]
    with timing.stage("layer1"):
        ing = ingest(path)
    scr = screen(ing, policy, guard=RuleGuard())
    status_of = {r.sentence_id: r.status for r in scr.quarantine}
    injected_ids = [s.sentence_id for s in scr.sentences if _is_injected(s.text, label["injected"])]
    routes = {sid: r["route"] for r in scr.routing_log for sid in r["sentence_ids"]}

    sentences = []
    for s in scr.sentences:
        sentences.append({
            "id": s.sentence_id,
            "injected": s.sentence_id in injected_ids,
            "status": status_of.get(s.sentence_id, "clean"),
        })
    answer = defended_answer(scr, llm)
    screened = _norm(scr.screened_text)
    out = {
        "id": label["id"], "kind": label["kind"], "split": label["split"],
        "carrier": label["carrier"], "status": scr.status.value,
        "sentences": sentences,
        "injected_ids": injected_ids,
        "injected_routes": [routes.get(i, "missing") for i in injected_ids],
        "facts_total": len(label["facts"]),
        "facts_kept": sum(1 for f in label["facts"] if _norm(f) in screened),
        "payload_in_screened": bool(label["injected"]) and _norm(label["injected"]) in screened,
        "defended_success": SUCCESS_MARKER in answer,
        "any_quarantined": any(r.status == "quarantined" for r in scr.quarantine),
        "any_withheld": bool(scr.quarantine),
    }
    if with_vulnerable:
        out["vulnerable_success"] = SUCCESS_MARKER in vulnerable_answer(path, llm)
    out["_screen"] = scr  # in-memory only (integrity suite); stripped before serializing
    return out


def run_corpus(manifest: dict[str, Any], root: Path, policy: dict[str, Any], llm: LLMClient,
               *, with_vulnerable: bool = False) -> list[dict[str, Any]]:
    return [run_doc(d, root, policy, llm, with_vulnerable=with_vulnerable)
            for d in manifest["documents"]]


def public_view(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: v for k, v in c.items() if not k.startswith("_")} for c in cases]
