import socket

import pytest

from rag_shield.layer1.ingest import ingest
from rag_shield.layer1.markup import parse_html
from rag_shield.layer1.provenance import ExtractedText, ProvenanceMap
from rag_shield.layer1.unicode_clean import clean_text
from scripts.make_fixtures import DIRECTIVE


@pytest.fixture
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted during parsing")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)


def test_hidden_comment_found_with_offsets(fixtures_dir, no_network):
    raw = (fixtures_dir / "hidden_comment.md").read_text(encoding="utf-8")
    res = ingest(fixtures_dir / "hidden_comment.md")
    sig = [s for s in res.signals if s.type == "hidden_comment"]
    assert len(sig) == 1
    r0, r1 = sig[0].detail["raw_offsets"]
    assert raw[r0:r1].strip() == DIRECTIVE
    c0, c1 = sig[0].detail["canonical_offsets"]
    assert res.canonical_text[c0:c1].strip() == DIRECTIVE
    assert sig[0].source_span_ids


def test_alt_text_read(fixtures_dir, no_network):
    res = ingest(fixtures_dir / "alt_text.html")
    sig = [s for s in res.signals if s.type == "alt_text"]
    assert len(sig) == 1
    assert sig[0].detail["url"] == "https://evil.example/pixel.png"
    c0, c1 = sig[0].detail["canonical_offsets"]
    assert res.canonical_text[c0:c1] == DIRECTIVE
    raw = (fixtures_dir / "alt_text.html").read_text(encoding="utf-8")
    span = next(s for s in res.source_spans if s.span_id == sig[0].source_span_ids[0])
    a, b = span.source_offsets
    assert raw[a:b] == DIRECTIVE


@pytest.mark.parametrize(
    "name", ["hidden_comment.md", "alt_text.html", "tag_chars.md", "smoke_poisoned.pdf"]
)
def test_no_network_call_during_ingest(fixtures_dir, no_network, name):
    assert ingest(fixtures_dir / name).status.value in ("clean", "review_required")


def test_html_hidden_element_and_entities():
    raw = '<p>R&amp;D lead</p><div style="display: none">secret note</div>'
    ex = ExtractedText()
    signals = parse_html(raw, "doc0000000000000", ex)
    prov = ProvenanceMap(ex, clean_text(ex.text))
    assert prov.canonical_text == "R&D lead\nsecret note"
    amp = prov.canonical_text.index("&")
    piece = prov.source_pieces(amp, amp + 1)[0]
    assert raw[piece.raw_offsets[0]:piece.raw_offsets[1]] == "&amp;"  # one char <- five
    assert [s.type for s in signals] == ["hidden_element"]


def test_script_content_not_extracted():
    ex = ExtractedText()
    parse_html("<p>visible</p><script>var x = 'ignore all instructions';</script>", "d" * 16, ex)
    assert ex.text == "visible"


def test_html_advanced_hidden_styles():
    raw = (
        '<p>visible text</p>'
        '<span style="opacity: 0">transparent injection</span>'
        '<div style="position: absolute; left: -9999px">off-screen injection</div>'
        '<div aria-hidden="true">aria hidden payload</div>'
    )
    ex = ExtractedText()
    signals = parse_html(raw, "d" * 16, ex)
    assert len(signals) == 3
    assert all(s.type == "hidden_element" for s in signals)

