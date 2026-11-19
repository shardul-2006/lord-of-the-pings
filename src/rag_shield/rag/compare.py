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


def naive_text(path: str | Path) -> str:
    """What an undefended RAG loader would read: plain PDF text or the raw file text.
    Unreadable files (encrypted, malformed...) give no text."""
    path = Path(path)
    try:
        if path.suffix.lower() == ".pdf":
            return extract_pdf_text(path)
        return path.read_bytes().decode("utf-8", errors="replace")
    except Exception:
        return ""


def _shield_chunks(path: str | Path) -> tuple[list[ScreenedChunk], str]:
    from rag_shield.shield import Shield

    shield = Shield(db_path=":memory:", keep_forensic=False)
    try:
        result = shield.ingest(path)
        return result.clean_chunks, f"shield:{result.screen.policy_version}"
    finally:
        shield.close()


def answer_both(
    path: str | Path,
    defended_chunks: list[ScreenedChunk],
    defense_label: str,
    llm: LLMClient,
    question: str = DEFAULT_QUESTION,
    spotlight_tier: str | None = None,
) -> dict[str, Trace]:
    """Vulnerable branch from the naive loader; defended branch from the given chunks only."""
    doc_sha = sha256_file(path)
    sentences = sentence_ids(doc_sha, split_sentences(naive_text(path)))
    pipe = RagPipeline()
    pipe.build_index([Chunk(chunk_id(doc_sha, i), doc_sha, g.text)
                      for i, g in enumerate(group_sentences(sentences), start=1)], "vulnerable")
    pipe.build_index(defended_chunks, "defended")
    return {
        "vulnerable": pipe.answer(question, "vulnerable", llm, doc_sha256=doc_sha),
        "defended": pipe.answer(question, "defended", llm, doc_sha256=doc_sha,
                                defense=defense_label, spotlight_tier=spotlight_tier),
    }


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
    if defense == "shield":
        # Full pipeline; unsupported / scan_failed documents contribute no chunks at all.
        defended_chunks, label = _shield_chunks(pdf_path)
    else:
        doc_sha = sha256_file(pdf_path)
        sentences = sentence_ids(doc_sha, split_sentences(naive_text(pdf_path)))
        kept, _dropped = defended_simple.filter_sentences(sentences)
        defended_chunks = [
            ScreenedChunk(chunk_id(doc_sha, i), g.sentence_ids, [], g.text)
            for i, g in enumerate(group_sentences(kept), start=1)
        ]
        label = defended_simple.DEFENSE_LABEL
    traces = answer_both(pdf_path, defended_chunks, label, llm, question, spotlight_tier)
    if out_dir is not None:
        for trace in traces.values():
            save_trace(trace, out_dir)
    return traces
