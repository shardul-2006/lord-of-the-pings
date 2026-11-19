from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from rag_shield.layer1.ingest import ingest
from rag_shield.layer1.provenance import ExtractedText, ProvenanceMap
from rag_shield.layer1.unicode_clean import clean_text
from rag_shield.models import SourceSpan

LINE1 = "Summary: the applicant designed a robust"
LINE2 = "pipeline for streaming sensor data."
SENTENCE = f"{LINE1}\n{LINE2}"


def _two_line_pdf(path):
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    c.setFont("Helvetica", 11)
    c.drawString(72, 700, "Header line.")
    c.drawString(72, 680, LINE1)
    c.drawString(72, 666, LINE2)
    c.showPage()
    c.save()


def _span(sid, start, text):
    return SourceSpan(sid, "doc", 1, (start, start + len(text)), [(0, 0, 1, 1)], text)


def test_nfkc_change_maps_back_to_source_spans():
    ex = ExtractedText()
    a, b = "ﬁnance", "école"
    ex.add_span(_span("A", 100, a), a)
    ex.add_separator("\n")
    ex.add_span(_span("B", 500, b), b)
    prov = ProvenanceMap(ex, clean_text(ex.text))
    assert prov.canonical_text == "finance\nécole"
    # "fi" (two canonical chars) <- one ligature char in span A
    pieces = prov.source_pieces(0, 2)
    assert [(p.span_id, p.raw_offsets) for p in pieces] == [("A", (100, 101))]
    # "é" (one canonical char) <- two source chars in span B
    e = prov.canonical_text.index("é")
    pieces = prov.source_pieces(e, e + 1)
    assert [(p.span_id, p.raw_offsets) for p in pieces] == [("B", (500, 502))]
    # the whole canonical text touches both spans, in order
    assert prov.source_span_ids(0, len(prov.canonical_text)) == ["A", "B"]


def test_sentence_spanning_two_pdf_lines(tmp_path):
    _two_line_pdf(tmp_path / "two_lines.pdf")
    res = ingest(tmp_path / "two_lines.pdf")
    prov = res.provenance
    start = res.canonical_text.index(SENTENCE)
    ids = prov.source_span_ids(start, start + len(SENTENCE))
    spans = {s.span_id: s for s in res.source_spans}
    assert [spans[i].original_text for i in ids] == [LINE1, LINE2]
    boxes = prov.highlight_boxes(start, start + len(SENTENCE))
    assert len(boxes) == 2
    (p1, b1), (p2, b2) = boxes
    assert p1 == p2 == 1 and b1[1] < b2[1]  # second line is lower on the page


def test_multi_span_highlight_is_word_precise(tmp_path):
    _two_line_pdf(tmp_path / "two_lines.pdf")
    res = ingest(tmp_path / "two_lines.pdf")
    prov = res.provenance
    phrase = "robust\npipeline"
    start = res.canonical_text.index(phrase)
    boxes = prov.highlight_boxes(start, start + len(phrase))
    assert len(boxes) == 2
    line1_box = next(s for s in res.source_spans if s.original_text == LINE1).bboxes[0]
    # highlight on line 1 starts at "robust", not at the line start
    assert boxes[0][1][0] > line1_box[0] + 100
    assert abs(boxes[0][1][2] - line1_box[2]) < 0.01


def test_canonical_spans_cover_source_text(fixtures_dir):
    res = ingest(fixtures_dir / "smoke_clean.pdf")
    by_id = {s.span_id: s for s in res.source_spans}
    for cs in res.canonical_spans:
        (sid,) = cs.source_span_ids
        c0, c1 = cs.canonical_offsets
        assert res.canonical_text[c0:c1] == by_id[sid].original_text


def test_markdown_spans_are_raw_file_offsets(fixtures_dir):
    raw = (fixtures_dir / "hidden_comment.md").read_text(encoding="utf-8")
    res = ingest(fixtures_dir / "hidden_comment.md")
    for s in res.source_spans:
        a, b = s.source_offsets
        assert raw[a:b] == s.original_text
