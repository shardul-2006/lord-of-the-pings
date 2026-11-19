"""PDF text extraction with layout hiding signals (Spec D).

Signals are SIGNALS, never deletion: hidden text stays in the extracted text, tagged.
- tiny_font:    font size below TINY_FONT_PT.
- low_contrast: WCAG contrast ratio against the background below MIN_CONTRAST. The background
                is assumed WHITE unless a filled rectangle lies under the word's centre.
- off_page:     the word's centre lies outside the page box.

Bounding boxes use pdfplumber coordinates: (x0, top, x1, bottom), origin top-left, points.
Text is grouped into lines, and each line into runs of words with the same style; every run
is one SourceSpan. PDF raw offsets are offsets in the extraction stream.
"""

from __future__ import annotations

from typing import Any

import pdfplumber

from rag_shield.layer1.provenance import ExtractedText
from rag_shield.models import BBox, Signal, SourceSpan

TINY_FONT_PT = 3.0
MIN_CONTRAST = 1.5
WHITE = (1.0, 1.0, 1.0)
LAYOUT_SIGNALS = ("tiny_font", "low_contrast", "off_page")


def to_rgb(color: Any) -> tuple[float, float, float]:
    """pdfplumber colour (gray / RGB / CMYK tuple, or None) -> RGB in [0, 1]. Unknown -> black."""
    if color is None:
        return (0.0, 0.0, 0.0)
    if isinstance(color, (int, float)):
        color = (color,)
    try:
        vals = [float(v) for v in color]
    except (TypeError, ValueError):
        return (0.0, 0.0, 0.0)  # pattern colours etc.
    if len(vals) == 1:
        return (vals[0],) * 3  # type: ignore[return-value]
    if len(vals) == 3:
        return (vals[0], vals[1], vals[2])
    if len(vals) == 4:
        c, m, y, k = vals
        return ((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))
    return (0.0, 0.0, 0.0)


def _lum(rgb: tuple[float, float, float]) -> float:
    def lin(v: float) -> float:
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(min(max(v, 0.0), 1.0)) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: tuple[float, float, float], bg: tuple[float, float, float]) -> float:
    a, b = sorted((_lum(fg), _lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def _background(page: Any, cx: float, cy: float) -> tuple[float, float, float]:
    bg = WHITE
    for rect in page.rects:  # later rects are drawn on top
        inside = rect["x0"] <= cx <= rect["x1"] and rect["top"] <= cy <= rect["bottom"]
        if rect.get("fill") and inside:
            bg = to_rgb(rect.get("non_stroking_color"))
    return bg


def _word_style(page: Any, w: dict[str, Any]) -> dict[str, Any]:
    cx, cy = (w["x0"] + w["x1"]) / 2, (w["top"] + w["bottom"]) / 2
    px0, ptop, px1, pbottom = page.bbox
    fg = to_rgb(w.get("non_stroking_color"))
    ratio = contrast_ratio(fg, _background(page, cx, cy))
    size = float(w.get("size") or 0.0)
    return {
        "tiny_font": size < TINY_FONT_PT,
        "low_contrast": ratio < MIN_CONTRAST,
        "off_page": not (px0 <= cx <= px1 and ptop <= cy <= pbottom),
        "size": round(size, 2),
        "color": tuple(round(v, 3) for v in fg),
        "contrast": round(ratio, 3),
    }


def _style_key(style: dict[str, Any]) -> tuple:
    return (style["tiny_font"], style["low_contrast"], style["off_page"], style["size"],
            style["color"])


def _lines(words: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    lines: list[list[dict[str, Any]]] = []
    for w in sorted(words, key=lambda w: (round(w["top"], 1), w["x0"])):
        size = float(w.get("size") or 1.0)
        if lines:
            ref = lines[-1][0]
            tol = max(0.25, 0.5 * min(size, float(ref.get("size") or 1.0)))
            if abs(w["top"] - ref["top"]) <= tol:
                lines[-1].append(w)
                continue
        lines.append([w])
    return [sorted(line, key=lambda w: w["x0"]) for line in lines]


def extract_pdf(pdf: Any, doc_id: str, ex: ExtractedText) -> list[Signal]:
    """Append every page's text to `ex` (one span per style run) and return layout signals."""
    signals: list[Signal] = []
    for page_no, page in enumerate(pdf.pages, start=1):
        words = page.extract_words(extra_attrs=["size", "non_stroking_color"])
        ex.add_separator("\n\n")
        for li, line in enumerate(_lines(words)):
            if li:
                ex.add_separator("\n")
            runs: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
            for w in line:
                style = _word_style(page, w)
                if runs and _style_key(runs[-1][0]) == _style_key(style):
                    runs[-1][1].append(w)
                else:
                    runs.append((style, [w]))
            for ri, (style, run_words) in enumerate(runs):
                if ri:
                    ex.add_separator(" ")
                signals.extend(_add_run(ex, doc_id, page_no, style, run_words))
    return signals


def _add_run(
    ex: ExtractedText, doc_id: str, page_no: int, style: dict[str, Any], words: list[dict]
) -> list[Signal]:
    text_parts: list[str] = []
    boxes: list[BBox | None] = []
    for k, w in enumerate(words):
        if k:
            text_parts.append(" ")
            boxes.append(None)
        box: BBox = (float(w["x0"]), float(w["top"]), float(w["x1"]), float(w["bottom"]))
        text_parts.append(w["text"])
        boxes.extend([box] * len(w["text"]))
    text = "".join(text_parts)
    word_boxes = [b for b in boxes if b is not None]
    run_box: BBox = (
        min(b[0] for b in word_boxes), min(b[1] for b in word_boxes),
        max(b[2] for b in word_boxes), max(b[3] for b in word_boxes),
    )
    start = len(ex.text)
    span = SourceSpan(
        span_id=f"{doc_id[:12]}-p{page_no}-o{start}",
        doc_id=doc_id,
        page=page_no,
        source_offsets=(start, start + len(text)),
        bboxes=[run_box],
        original_text=text,
    )
    ex.add_span(span, text, char_box=boxes)
    detail = {"size": style["size"], "color": list(style["color"]), "contrast": style["contrast"]}
    return [
        Signal(kind, page=page_no, bbox=run_box, source_span_ids=[span.span_id], detail=detail)
        for kind in LAYOUT_SIGNALS
        if style[kind]
    ]


def pdf_layout_signals(path: str) -> list[Signal]:
    """Convenience: layout signals for a PDF on disk (no metadata, no Unicode cleaning)."""
    with pdfplumber.open(path) as pdf:
        return extract_pdf(pdf, "adhoc", ExtractedText())
