from rag_shield.layer1.unicode_clean import ZWJ, ZWNJ, clean_text, is_tag
from scripts.make_fixtures import DIRECTIVE


def _read(fixtures_dir, name):
    return (fixtures_dir / name).read_text(encoding="utf-8")


def _assert_map_consistent(src: str, res) -> None:
    assert len(res.char_map) == len(res.text)
    for a, b in res.char_map:
        assert 0 <= a < b <= len(src)


def test_tag_payload_removed_and_logged(fixtures_dir):
    src = _read(fixtures_dir, "tag_chars.md")
    res = clean_text(src)
    assert not any(is_tag(c) for c in res.text)
    tag_logs = [r for r in res.removals if r["kind"] == "unicode_tag"]
    assert len(tag_logs) == 1
    assert tag_logs[0]["decoded"] == DIRECTIVE
    assert tag_logs[0]["count"] == len(DIRECTIVE)
    assert "Skills: Python, SQL" in res.text
    _assert_map_consistent(src, res)


def test_zero_width_run_removed(fixtures_dir):
    res = clean_text("Ig​‌​nore this")
    assert res.text == "Ignore this"
    assert res.removals == [{"kind": "zero_width_run", "offset": 2, "count": 3}]
    fixture = clean_text(_read(fixtures_dir, "zero_width_run.md"))
    assert DIRECTIVE in fixture.text  # the split directive is readable again for Layer 2


def test_single_joiners_preserved():
    for s in (f"क्{ZWJ}ष", f"क्{ZWNJ}ष", f"క్{ZWNJ}ష"):
        res = clean_text(s)
        assert res.text == s
        assert res.removals == []


def test_lone_zero_width_space_removed_and_logged():
    res = clean_text("a​b")
    assert res.text == "ab"
    assert res.removals[0]["kind"] == "zero_width_char"


def test_indic_fixture_unchanged(fixtures_dir):
    src = _read(fixtures_dir, "indic_zwj.md")
    assert ZWJ in src and ZWNJ in src
    res = clean_text(src)
    assert res.text == src
    assert res.removals == [] and res.transforms == []


def test_emoji_flag_handled_and_logged(fixtures_dir):
    src = _read(fixtures_dir, "emoji_flag.md")
    res = clean_text(src)
    assert "\U0001F3F4" in res.text
    assert not any(is_tag(c) for c in res.text)
    logs = [r for r in res.removals if r["kind"] == "unicode_tag"]
    assert logs and logs[0]["context"] == "emoji_flag_tag_sequence"


def test_bidi_controls_removed():
    res = clean_text("abc‮def‬ ghi⁦x⁩")
    assert res.text == "abcdef ghix"
    assert {r["kind"] for r in res.removals} == {"bidi_control"}


def test_nfkc_applied_with_mapping():
    src = "ﬁne Ａ é"
    res = clean_text(src)
    assert res.text == "fine A é"
    assert res.char_map[0] == res.char_map[1] == (0, 1)  # one-to-many: ligature
    assert res.char_map[-1] == (6, 8)  # many-to-one: e + combining acute (src[6:8])
    assert {t["kind"] for t in res.transforms} == {"nfkc"}
