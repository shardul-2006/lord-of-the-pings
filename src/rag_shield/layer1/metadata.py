"""PDF document properties as carrier signals.

Content-bearing fields are appended to the extracted text as their own spans (page=None), so
Layer 2 can score and quarantine a directive hidden there. Tool-generated fields and dates
are reported in the signal detail only.
"""

from __future__ import annotations

from typing import Any

from rag_shield.layer1.provenance import ExtractedText
from rag_shield.models import Signal, SourceSpan

TEXT_FIELDS = ("Title", "Author", "Subject", "Keywords")
PLACEHOLDERS = frozenset({"", "unspecified", "(unspecified)", "anonymous", "(anonymous)"})


def _as_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value).strip() if value is not None else ""


def extract_metadata(meta: dict[str, Any] | None, doc_id: str, ex: ExtractedText) -> list[Signal]:
    meta = meta or {}
    signals: list[Signal] = []
    for name in TEXT_FIELDS:
        value = _as_text(meta.get(name))
        if value.lower() in PLACEHOLDERS:
            continue
        ex.add_separator("\n\n" if not signals else "\n")
        start = len(ex.text)
        span = SourceSpan(
            span_id=f"{doc_id[:12]}-meta-{name.lower()}",
            doc_id=doc_id,
            page=None,
            source_offsets=(start, start + len(value)),
            bboxes=[],
            original_text=value,
        )
        ex.add_span(span, value)
        signals.append(Signal("metadata", source_span_ids=[span.span_id], detail={"field": name}))
    return signals


def other_properties(meta: dict[str, Any] | None) -> dict[str, str]:
    """Non-text properties (Creator, Producer, dates...) for the record, not for the LLM."""
    return {k: _as_text(v) for k, v in (meta or {}).items() if k not in TEXT_FIELDS}
