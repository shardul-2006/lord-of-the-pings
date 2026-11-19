import random

from rag_shield.layer3.spotlight import DATAMARK, spotlight, wrap
from rag_shield.models import ScreenedChunk
from rag_shield.rag.compare import compare
from rag_shield.rag.llm import MockLLM

CHUNKS = [
    ScreenedChunk("d-c1", ["s1"], [], "Skills: Python, SQL"),
    ScreenedChunk("d-c2", ["s2"], [], "Intern at Acme Labs."),
]


def test_two_calls_produce_different_tags():
    a, b = spotlight(CHUNKS), spotlight(CHUNKS)
    assert a.tag != b.tag and a.tag.startswith("UNTRUSTED_")
    assert wrap(CHUNKS, "external_upload") != wrap(CHUNKS, "external_upload")


def test_seeded_rng_is_reproducible():
    a = spotlight(CHUNKS, rng=random.Random(1))
    b = spotlight(CHUNKS, rng=random.Random(1))
    assert a.tag == b.tag


def test_datamark_present_for_external_upload():
    s = spotlight(CHUNKS, "external_upload")
    assert s.datamark is True
    assert f"Skills:{DATAMARK}Python,{DATAMARK}SQL" in s.text


def test_internal_kb_is_not_datamarked():
    s = spotlight(CHUNKS, "internal_kb")
    assert s.datamark is False and "Skills: Python, SQL" in s.text


def test_reminder_after_context():
    s = spotlight(CHUNKS)
    close = s.text.index(f"<</{s.tag}>>")
    assert s.text.index("REMINDER") > close
    assert s.text.index("[d-c2]") < close
    assert s.text.count(s.tag) >= 3  # open, close, reminder


def test_tag_recorded_in_trace(fixtures_dir):
    traces = compare(fixtures_dir / "smoke_poisoned.pdf", MockLLM(), defense="shield",
                     spotlight_tier="external_upload")
    d = traces["defended"]
    assert d.spotlight["tag"] in d.prompt
    assert d.spotlight["tier"] == "external_upload" and d.spotlight["datamark"] is True
    assert traces["vulnerable"].spotlight is None
    assert "HIRE AS CEO" not in d.output
