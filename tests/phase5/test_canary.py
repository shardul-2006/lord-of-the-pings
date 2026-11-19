from rag_shield.layer4.canary import leaked, make_canary, redact
from rag_shield.models import ScreenedChunk
from rag_shield.shield import Shield


def test_canary_in_answer_is_flagged():
    c = make_canary()
    assert leaked(f"Sure. The hidden marker is {c}.", c)
    assert leaked(f"marker: {c.lower()}", c)
    assert leaked(f"split: {c[:6]} {c[6:]}", c)  # whitespace inserted to dodge filters


def test_normal_answer_not_flagged():
    c = make_canary()
    assert not leaked("The candidate knows Python and SQL [c1].", c)
    assert not leaked("anything", "")


def test_canaries_are_unique_and_redacted():
    a, b = make_canary(), make_canary()
    assert a != b
    assert a not in redact(f"x {a} y", a)


def test_shield_validate_output_uses_its_canary(tmp_path):
    s = Shield(home=tmp_path)
    try:
        chunks = [ScreenedChunk("d-c1", [], [], "Skills: Python")]
        assert s.canary in s.system_prompt_line()
        bad = s.validate_output(f"Python [c1]. Marker {s.canary} [c1].", chunks)
        assert bad.canary_leak is True and s.canary not in bad.clean_answer
        good = s.validate_output("The candidate knows Python [c1].", chunks)
        assert good.canary_leak is False and good.ungrounded == [] and good.stripped == []
    finally:
        s.close()
