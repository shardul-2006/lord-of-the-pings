from rag_shield.layer1.ingest import ingest
from rag_shield.layer2 import screen
from rag_shield.layer2.fusion import CLEAN, QUARANTINED, REVIEW_REQUIRED, fuse
from rag_shield.layer2.guard import FakeGuard
from rag_shield.policy import load_policy


def test_hiding_plus_directive_is_quarantined_even_with_low_semantic():
    f = fuse(semantic=0.0, linguistic=0.9, hiding=1.0, carrier=False, policy=load_policy())
    assert f.disposition == QUARANTINED and f.reason.startswith("rule:hiding+directive")


def test_trigger_word_only_is_clean():
    f = fuse(semantic=0.07, linguistic=0.0, hiding=0.0, carrier=False, policy=load_policy())
    assert f.disposition == CLEAN


def test_ambiguous_is_review_required():
    f = fuse(semantic=0.6, linguistic=0.5, hiding=0.0, carrier=False, policy=load_policy())
    assert 0.4 <= f.score < 0.7
    assert f.disposition == REVIEW_REQUIRED


def test_carrier_alone_stays_clean_but_amplifies_directives():
    p = load_policy()
    assert fuse(0.03, 0.0, 0.0, True, p).disposition == CLEAN
    plain = fuse(0.6, 0.5, 0.0, False, p)
    carried = fuse(0.6, 0.5, 0.0, True, p)
    assert carried.score > plain.score


def test_thresholds_come_from_policy():
    strict = load_policy(overrides={"thresholds": {"quarantine": 0.3}})
    assert fuse(0.6, 0.5, 0.0, False, strict).disposition == QUARANTINED


def test_trigger_word_fixture_is_clean(fixtures_dir):
    res = screen(ingest(fixtures_dir / "smoke_trigger_words.pdf"), guard=FakeGuard())
    assert res.status.value == "clean"
    assert "system override module" in res.screened_text
    assert res.quarantine == []
