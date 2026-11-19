import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from rag_shield.layer1.ingest import ingest
from rag_shield.layer1.pdf_signals import LAYOUT_SIGNALS, pdf_layout_signals
from scripts.make_fixtures import DIRECTIVE


@pytest.mark.parametrize(
    "name, kind",
    [
        ("tiny_font.pdf", "tiny_font"),
        ("white_on_white.pdf", "low_contrast"),
        ("off_page.pdf", "off_page"),
        ("smoke_poisoned.pdf", "tiny_font"),
        ("smoke_poisoned.pdf", "low_contrast"),
    ],
)
def test_carrier_signal_on_page_one_with_bbox(fixtures_dir, name, kind):
    res = ingest(fixtures_dir / name)
    sigs = [s for s in res.signals if s.type == kind]
    assert sigs, f"{kind} not found in {name}"
    s = sigs[0]
    assert s.page == 1
    assert s.bbox is not None and s.bbox[0] < s.bbox[2] and s.bbox[1] < s.bbox[3]
    c0, c1 = s.detail["canonical_offsets"]
    assert res.canonical_text[c0:c1] == DIRECTIVE


def test_off_page_bbox_outside_page(fixtures_dir):
    s = next(s for s in pdf_layout_signals(str(fixtures_dir / "off_page.pdf")))
    assert s.type == "off_page" and s.bbox[0] > A4[0]


def test_clean_pdf_has_no_layout_signals(fixtures_dir):
    for name in ("smoke_clean.pdf", "smoke_trigger_words.pdf", "visible_injection.pdf"):
        assert [s for s in pdf_layout_signals(str(fixtures_dir / name))] == []


def test_metadata_payload_is_a_carrier_span(fixtures_dir):
    res = ingest(fixtures_dir / "metadata_payload.pdf")
    subj = [s for s in res.signals if s.type == "metadata" and s.detail["field"] == "Subject"]
    assert len(subj) == 1
    c0, c1 = subj[0].detail["canonical_offsets"]
    assert res.canonical_text[c0:c1] == DIRECTIVE
    assert not any(s.type in LAYOUT_SIGNALS for s in res.signals)


def _pdf(path, draw):
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    draw(c)
    c.showPage()
    c.save()


def test_white_text_on_dark_rect_is_not_low_contrast(tmp_path):
    def draw(c):
        c.setFillColorRGB(0.1, 0.1, 0.3)
        c.rect(60, 690, 300, 30, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica", 11)
        c.drawString(72, 700, "Banner heading in white on navy")

    _pdf(tmp_path / "banner.pdf", draw)
    assert pdf_layout_signals(str(tmp_path / "banner.pdf")) == []


def test_light_grey_on_white_is_low_contrast(tmp_path):
    def draw(c):
        c.setFillColorRGB(0.95, 0.95, 0.95)
        c.setFont("Helvetica", 11)
        c.drawString(72, 700, "Barely visible grey text")

    _pdf(tmp_path / "grey.pdf", draw)
    assert [s.type for s in pdf_layout_signals(str(tmp_path / "grey.pdf"))] == ["low_contrast"]
