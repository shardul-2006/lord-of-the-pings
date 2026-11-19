"""RAG pipeline: index screened chunks and answer questions. Phase 0 stub."""

from __future__ import annotations

from rag_shield._stub import stub_reason
from rag_shield.models import IndexInfo, ScreenedChunk, Trace
from rag_shield.rag.llm import LLMClient


def build_index(chunks: list[ScreenedChunk], namespace: str) -> IndexInfo:
    return IndexInfo(namespace=namespace, index_version=0, chunk_ids=[])


def answer(question: str, namespace: str, llm: LLMClient) -> Trace:
    return Trace(
        branch=namespace,
        doc_sha256="",
        retrieved_chunk_ids=[],
        prompt="",
        model=llm.model_id,
        settings={},
        output=stub_reason("answer"),
        defense="none",
    )
