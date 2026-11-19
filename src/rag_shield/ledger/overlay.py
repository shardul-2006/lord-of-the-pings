"""Evidence overlay: render the ORIGINAL PDF page with withheld sentences highlighted.

Boxes come from the provenance map (one per source span, word-precise), in pdfplumber
coordinates (x0, top, x1, bottom), which match PyMuPDF's unrotated page coordinates.
Tiny boxes are padded so 0.5 pt text is still visible; off-page text is marked by a band
on the nearest page edge. A legend lists the signals that fired.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pymupdf

QUARANTINE_STROKE = (0.85, 0.0, 0.0)
REVIEW_STROKE = (0.95, 0.5, 0.0)
HIGHLIGHT_FILL = (1.0, 0.85, 0.0)
FILL_OPACITY = 0.45
MIN_HEIGHT = 6.0
PAD = 1.5
EDGE_BAND = 8.0
DEFAULT_ZOOM = 2.0


def _target_rect(bbox: tuple[float, float, float, float], page_rect: Any) -> tuple[Any, bool]:
    x0, top, x1, bottom = bbox
    cy = (top + bottom) / 2
    if bottom - top < MIN_HEIGHT:
        top, bottom = cy - MIN_HEIGHT / 2, cy + MIN_HEIGHT / 2
    rect = pymupdf.Rect(x0 - PAD, top - PAD, x1 + PAD, bottom + PAD)
    clipped = rect & page_rect
    if not clipped.is_empty and clipped.width > 0.5:
        return clipped, False
    # entirely off the page: mark the nearest edge at the same height
    y0 = min(max(top, page_rect.y0), page_rect.y1 - MIN_HEIGHT)
    y1 = y0 + max(MIN_HEIGHT, bottom - top)
    if x0 >= page_rect.x1:
        return pymupdf.Rect(page_rect.x1 - EDGE_BAND, y0, page_rect.x1, y1), True
    return pymupdf.Rect(page_rect.x0, y0, page_rect.x0 + EDGE_BAND, y1), True


def _render(doc: Any, page_no: int, zoom: float) -> bytes:
    pix = doc[page_no - 1].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    return pix.tobytes("png")


def render_page(pdf_path: str | Path, page: int, zoom: float = DEFAULT_ZOOM) -> bytes:
    """Plain render of a page (no highlights), as PNG bytes."""
    with pymupdf.open(str(pdf_path)) as doc:
        return _render(doc, page, zoom)


def render_overlay(
    pdf_path: str | Path,
    page: int,
    highlights: list[dict[str, Any]],
    zoom: float = DEFAULT_ZOOM,
    legend: bool = True,
) -> bytes:
    """PNG bytes of `page` (1-based) with highlights drawn.

    highlights: [{"bbox": [x0, top, x1, bottom], "status": "quarantined"|"review_required",
                  "signals": [...], "label": "..."}]
    """
    with pymupdf.open(str(pdf_path)) as doc:
        if not 1 <= page <= doc.page_count:
            raise ValueError(f"page {page} out of range 1..{doc.page_count}")
        pg = doc[page - 1]
        page_rect = pg.rect
        legend_lines: list[str] = []
        for h in highlights:
            rect, off_page = _target_rect(tuple(h["bbox"]), page_rect)
            stroke = QUARANTINE_STROKE if h.get("status") == "quarantined" else REVIEW_STROKE
            pg.draw_rect(rect, color=stroke, fill=HIGHLIGHT_FILL, fill_opacity=FILL_OPACITY,
                         width=1.2, overlay=True)
            line = f"{h.get('status', 'finding')}: {', '.join(h.get('signals', [])) or '-'}"
            if off_page:
                line += " (off-page text, marked at page edge)"
            if line not in legend_lines:
                legend_lines.append(line)
        if legend and legend_lines:
            _draw_legend(pg, legend_lines)
        return _render(doc, page, zoom)


def _draw_legend(pg: Any, lines: list[str]) -> None:
    text = "RAG-Shield evidence\n" + "\n".join(lines)
    height = 10 + 9 * (len(lines) + 1)
    r = pymupdf.Rect(8, pg.rect.y1 - height - 8, 330, pg.rect.y1 - 8)
    pg.draw_rect(r, color=(0.3, 0.3, 0.3), fill=(1, 1, 1), width=0.6, overlay=True)
    pg.insert_textbox(r + (4, 3, -4, -3), text, fontsize=7, color=(0.1, 0.1, 0.1))


def highlights_from_findings(findings: list[dict[str, Any]], page: int) -> list[dict[str, Any]]:
    """Ledger findings rows -> highlight dicts for one page (withheld sentences only)."""
    out = []
    for f in findings:
        if f["status"] not in ("quarantined", "review_required"):
            continue
        signals = sorted({s["type"] for s in f["signals"]})
        for pg, bbox in f["highlights"]:
            if pg == page and bbox:
                out.append({"bbox": bbox, "status": f["status"], "signals": signals,
                            "sentence_id": f["sentence_id"]})
    return out
