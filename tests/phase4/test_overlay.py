import numpy as np
import pymupdf

from rag_shield.ledger.overlay import DEFAULT_ZOOM, MIN_HEIGHT, PAD, render_page

LEGEND_BAND_PT = 90  # legend lives in the bottom band of the page


def _pixels(png: bytes) -> np.ndarray:
    pix = pymupdf.Pixmap(png)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)


def _highlight_boxes(shield, doc_id):
    rows = shield.ledger.findings_for(doc_id)
    return [bbox for f in rows if f["status"] == "quarantined" for _, bbox in f["highlights"]]


def _region(bbox, margin):
    x0, top, x1, bottom = bbox
    cy = (top + bottom) / 2
    half = max((bottom - top) / 2, MIN_HEIGHT / 2) + PAD + margin
    z = DEFAULT_ZOOM
    return (int((x0 - PAD - margin) * z), int((cy - half) * z),
            int((x1 + PAD + margin) * z) + 1, int((cy + half) * z) + 1)


def test_highlight_inside_bbox_and_nothing_outside(make_shield, fixtures_dir):
    shield = make_shield()
    res = shield.ingest(fixtures_dir / "smoke_poisoned.pdf")
    png = shield.overlay(res.doc_id, 1)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    over = _pixels(png).astype(int)
    plain = _pixels(render_page(fixtures_dir / "smoke_poisoned.pdf", 1)).astype(int)
    assert over.shape == plain.shape

    (bbox,) = _highlight_boxes(shield, res.doc_id)
    x0, y0, x1, y1 = _region(bbox, 0)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    r, g, b = over[cy, cx][:3]
    assert tuple(plain[cy, cx][:3]) == (255, 255, 255)  # white-on-white: invisible in plain
    assert r > 200 and b < 200 and (r, g, b) != (255, 255, 255)  # amber highlight

    changed = np.any(over != plain, axis=2)
    allowed = np.zeros_like(changed)
    ax0, ay0, ax1, ay1 = _region(bbox, 2)
    allowed[max(ay0, 0):ay1, max(ax0, 0):ax1] = True
    allowed[-int(LEGEND_BAND_PT * DEFAULT_ZOOM):, :] = True
    assert changed.any()
    assert not (changed & ~allowed).any(), "overlay changed pixels outside the finding"


def test_multi_span_highlight(make_shield, wrapped_directive_pdf):
    shield = make_shield()
    res = shield.ingest(wrapped_directive_pdf)
    assert res.status.value == "flagged"
    assert len(res.quarantined_ids) == 1  # one sentence across two lines
    boxes = _highlight_boxes(shield, res.doc_id)
    assert len(boxes) == 2 and boxes[0][1] < boxes[1][1]
    over = _pixels(shield.overlay(res.doc_id, 1)).astype(int)
    for bbox in boxes:
        x0, y0, x1, y1 = _region(bbox, 0)
        r, g, b = over[(y0 + y1) // 2, (x0 + x1) // 2][:3]
        assert r > 200 and b < 200


def test_off_page_marked_at_edge(make_shield, fixtures_dir):
    shield = make_shield()
    res = shield.ingest(fixtures_dir / "off_page.pdf")
    over = _pixels(shield.overlay(res.doc_id, 1)).astype(int)
    plain = _pixels(render_page(fixtures_dir / "off_page.pdf", 1)).astype(int)
    right_edge = np.any(over[:, -10:] != plain[:, -10:], axis=2)
    assert right_edge.any()


def test_overlay_rejects_non_pdf(make_shield, fixtures_dir):
    shield = make_shield()
    res = shield.ingest(fixtures_dir / "hidden_comment.md")
    try:
        shield.overlay(res.doc_id, 1)
    except ValueError as e:
        assert "PDF" in str(e)
    else:
        raise AssertionError("expected ValueError")
