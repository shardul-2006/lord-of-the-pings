"""Canonical -> source provenance (Spec B).

Coordinates:
- raw offsets: SourceSpan.source_offsets. Character offsets in the original file text for
  Markdown/HTML; offsets in the extraction stream for PDF (PDF has no character stream).
- extracted offsets: positions in the extracted text (spans joined with separators).
- canonical offsets: positions in the cleaned text.

Mappings are one-to-many and many-to-one (NFKC, entity decoding), so ranges are returned as
lists of per-span pieces, and highlights as one bbox per span.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rag_shield.layer1.unicode_clean import CleanResult
from rag_shield.models import BBox, CanonicalSpan, SourceSpan


@dataclass
class ExtractedText:
    text: str = ""
    spans: list[SourceSpan] = field(default_factory=list)
    char_span: list[int | None] = field(default_factory=list)  # span index; None = separator
    char_raw: list[tuple[int, int] | None] = field(default_factory=list)  # raw range per char
    char_box: list[BBox | None] = field(default_factory=list)  # word bbox (PDF only)

    def add_separator(self, sep: str) -> None:
        if not self.text or not sep:
            return
        self.text += sep
        self.char_span.extend([None] * len(sep))
        self.char_raw.extend([None] * len(sep))
        self.char_box.extend([None] * len(sep))

    def add_span(
        self,
        span: SourceSpan,
        text: str,
        char_raw: list[tuple[int, int]] | None = None,
        char_box: list[BBox | None] | None = None,
    ) -> None:
        """Append `text` for `span`. Default raw mapping: consecutive from source_offsets[0]."""
        idx = len(self.spans)
        self.spans.append(span)
        base = span.source_offsets[0]
        raw = char_raw or [(base + k, base + k + 1) for k in range(len(text))]
        boxes = char_box or [None] * len(text)
        if not (len(raw) == len(boxes) == len(text)):
            raise ValueError("per-char raw/box lists must match text length")
        self.text += text
        self.char_span.extend([idx] * len(text))
        self.char_raw.extend(raw)
        self.char_box.extend(boxes)


@dataclass
class SourcePiece:
    span_id: str
    page: int | None
    raw_offsets: tuple[int, int]
    bboxes: list[BBox]


def _union(boxes: list[BBox]) -> BBox:
    return (
        min(b[0] for b in boxes), min(b[1] for b in boxes),
        max(b[2] for b in boxes), max(b[3] for b in boxes),
    )


class ProvenanceMap:
    def __init__(self, extracted: ExtractedText, cleaned: CleanResult) -> None:
        self.extracted = extracted
        self.cleaned = cleaned
        self.canonical_text = cleaned.text

    # --- canonical -> extracted / source -------------------------------------------------
    def extracted_range(self, c_start: int, c_end: int) -> tuple[int, int]:
        cmap = self.cleaned.char_map[c_start:c_end]
        if not cmap:
            raise ValueError(f"empty canonical range {c_start}:{c_end}")
        return min(a for a, _ in cmap), max(b for _, b in cmap)

    def source_pieces(self, c_start: int, c_end: int) -> list[SourcePiece]:
        """One piece per source span touched by the canonical range, in reading order."""
        e_start, e_end = self.extracted_range(c_start, c_end)
        ex = self.extracted
        order: list[int] = []
        raws: dict[int, list[tuple[int, int]]] = {}
        boxes: dict[int, list[BBox]] = {}
        for k in range(e_start, e_end):
            si = ex.char_span[k]
            if si is None:
                continue
            if si not in raws:
                order.append(si)
                raws[si], boxes[si] = [], []
            raws[si].append(ex.char_raw[k])  # type: ignore[arg-type]
            if ex.char_box[k] is not None:
                boxes[si].append(ex.char_box[k])  # type: ignore[arg-type]
        pieces = []
        for si in order:
            span = ex.spans[si]
            raw = (min(a for a, _ in raws[si]), max(b for _, b in raws[si]))
            # one bbox per distinct word box run; merged into a single box per span
            bbs = [_union(boxes[si])] if boxes[si] else list(span.bboxes)
            pieces.append(SourcePiece(span.span_id, span.page, raw, bbs))
        return pieces

    def source_span_ids(self, c_start: int, c_end: int) -> list[str]:
        return [p.span_id for p in self.source_pieces(c_start, c_end)]

    def highlight_boxes(self, c_start: int, c_end: int) -> list[tuple[int | None, BBox]]:
        """(page, bbox) per span, for multi-span evidence highlighting."""
        return [(p.page, b) for p in self.source_pieces(c_start, c_end) for b in p.bboxes]

    # --- extracted -> canonical ----------------------------------------------------------
    def canonical_range(self, e_start: int, e_end: int) -> tuple[int, int]:
        """Smallest canonical range covering extracted [e_start, e_end).
        Zero-length (insertion point) when everything there was removed."""
        hits = [i for i, (a, b) in enumerate(self.cleaned.char_map) if a < e_end and b > e_start]
        if hits:
            return hits[0], hits[-1] + 1
        pos = sum(1 for a, _ in self.cleaned.char_map if a < e_start)
        return pos, pos

    def span_extracted_range(self, span_id: str) -> tuple[int, int]:
        idx = next(i for i, s in enumerate(self.extracted.spans) if s.span_id == span_id)
        ks = [k for k, si in enumerate(self.extracted.char_span) if si == idx]
        return (ks[0], ks[-1] + 1) if ks else (0, 0)

    def canonical_spans(self) -> list[CanonicalSpan]:
        result = []
        for span in self.extracted.spans:
            e0, e1 = self.span_extracted_range(span.span_id)
            c0, c1 = self.canonical_range(e0, e1)
            log: list[dict[str, Any]] = [
                t for t in self.cleaned.transforms + self.cleaned.removals
                if t["offset"] < e1 and t["offset"] + t["count"] > e0
            ]
            result.append(CanonicalSpan((c0, c1), [span.span_id], log))
        return result
