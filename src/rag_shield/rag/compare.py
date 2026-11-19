"""Run the vulnerable and defended branches on one document with identical settings."""

from __future__ import annotations

from pathlib import Path

from rag_shield.models import Chunk, ScreenedChunk, Trace
from rag_shield.rag import defended_simple
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
from rag_shield.rag.trace import save_trace

DEFENSES = ("shield", "simple")


def _shield_chunks(pdf_path: str | Path) -> tuple[list[ScreenedChunk], str]:
    from rag_shield.shield import Shield

    shield = Shield(db_path=":memory:", keep_forensic=False)
    try:
        result = shield.ingest(pdf_path)
        return result.clean_chunks, f"shield:{result.screen.policy_version}"
    finally:
        shield.close()


def compare(
    pdf_path: str | Path,
    llm: LLMClient,
    defense: str = "simple",
    question: str = DEFAULT_QUESTION,
    out_dir: str | Path | None = None,
    spotlight_tier: str | None = None,
) -> dict[str, Trace]:
    """`spotlight_tier` wraps the DEFENDED context with Layer 3 spotlighting."""
    if defense not in DEFENSES:
        raise ValueError(f"unknown defense {defense!r}; available: {DEFENSES}")
    doc_sha = sha256_file(pdf_path)
    try:
        raw_text = extract_pdf_text(pdf_path)
    except Exception:  # the naive pipeline cannot read it either (encrypted, malformed...)
        raw_text = ""
    sentences = sentence_ids(doc_sha, split_sentences(raw_text))
    pipe = RagPipeline()

    vulnerable_chunks = [
        Chunk(chunk_id(doc_sha, i), doc_sha, g.text)
        for i, g in enumerate(group_sentences(sentences), start=1)
    ]
    pipe.build_index(vulnerable_chunks, "vulnerable")

    if defense == "shield":
        # Full pipeline; unsupported / scan_failed documents contribute no chunks at all.
        defended_chunks, label = _shield_chunks(pdf_path)
    else:
        kept, _dropped = defended_simple.filter_sentences(sentences)
        defended_chunks = [
            ScreenedChunk(chunk_id(doc_sha, i), g.sentence_ids, [], g.text)
            for i, g in enumerate(group_sentences(kept), start=1)
        ]
        label = defended_simple.DEFENSE_LABEL
    pipe.build_index(defended_chunks, "defended")

    traces = {
        "vulnerable": pipe.answer(question, "vulnerable", llm, doc_sha256=doc_sha),
        "defended": pipe.answer(question, "defended", llm, doc_sha256=doc_sha, defense=label,
                                spotlight_tier=spotlight_tier),
    }
    if out_dir is not None:
        for trace in traces.values():
            save_trace(trace, out_dir)
    return traces
