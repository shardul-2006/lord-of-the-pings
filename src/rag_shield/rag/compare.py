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

DEFENSES = ("simple",)


def compare(
    pdf_path: str | Path,
    llm: LLMClient,
    defense: str = "simple",
    question: str = DEFAULT_QUESTION,
    out_dir: str | Path | None = None,
) -> dict[str, Trace]:
    if defense not in DEFENSES:
        raise ValueError(f"unknown defense {defense!r}; available: {DEFENSES}")
    doc_sha = sha256_file(pdf_path)
    sentences = sentence_ids(doc_sha, split_sentences(extract_pdf_text(pdf_path)))
    pipe = RagPipeline()

    vulnerable_chunks = [
        Chunk(chunk_id(doc_sha, i), doc_sha, g.text)
        for i, g in enumerate(group_sentences(sentences), start=1)
    ]
    pipe.build_index(vulnerable_chunks, "vulnerable")

    kept, _dropped = defended_simple.filter_sentences(sentences)
    defended_chunks = [
        ScreenedChunk(chunk_id(doc_sha, i), g.sentence_ids, [], g.text)
        for i, g in enumerate(group_sentences(kept), start=1)
    ]
    pipe.build_index(defended_chunks, "defended")

    traces = {
        "vulnerable": pipe.answer(question, "vulnerable", llm, doc_sha256=doc_sha),
        "defended": pipe.answer(
            question, "defended", llm, doc_sha256=doc_sha, defense=defended_simple.DEFENSE_LABEL
        ),
    }
    if out_dir is not None:
        for trace in traces.values():
            save_trace(trace, out_dir)
    return traces
