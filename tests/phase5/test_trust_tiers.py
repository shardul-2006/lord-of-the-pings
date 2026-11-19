import pytest

from rag_shield.layer1.ingest import ingest
from rag_shield.layer2 import screen
from rag_shield.layer2.fusion import fuse
from rag_shield.layer2.guard import FakeGuard
from rag_shield.layer3.trust_tiers import apply_tier
from rag_shield.policy import load_policy
from rag_shield.shield import Shield
from scripts.make_fixtures import DIRECTIVE


def test_external_upload_is_stricter():
    ext = apply_tier(load_policy(), "external_upload")
    kb = apply_tier(load_policy(), "internal_kb")
    assert ext["thresholds"]["quarantine"] < kb["thresholds"]["quarantine"]
    assert ext["thresholds"]["review"] < kb["thresholds"]["review"]
    assert ext["tier"] == "external_upload" and kb["tier"] == "internal_kb"


def test_same_borderline_sentence_differs_by_tier(fixtures_dir):
    """visible_injection: a directive in normal visible text (no hiding signal), score ~0.79."""
    ing = ingest(fixtures_dir / "visible_injection.pdf")
    ext = screen(ing, apply_tier(load_policy(), "external_upload"), guard=FakeGuard())
    kb = screen(ing, apply_tier(load_policy(), "internal_kb"), guard=FakeGuard())
    assert ext.status.value == "flagged" and DIRECTIVE not in ext.screened_text
    assert kb.status.value == "clean" and DIRECTIVE in kb.screened_text


def test_hard_rule_holds_in_every_tier():
    kb = apply_tier(load_policy(), "internal_kb")
    assert fuse(0.0, 0.9, 1.0, False, kb).disposition == "quarantined"


def test_hidden_directive_quarantined_even_internal(fixtures_dir):
    ing = ingest(fixtures_dir / "smoke_poisoned.pdf")
    kb = screen(ing, apply_tier(load_policy(), "internal_kb"), guard=FakeGuard())
    assert kb.status.value == "flagged"


def test_shield_uses_its_tier(tmp_path, fixtures_dir):
    s = Shield(source_tier="internal_kb", home=tmp_path, guard=FakeGuard())
    try:
        assert s.policy["tier"] == "internal_kb"
        assert s.ingest(fixtures_dir / "visible_injection.pdf").status.value == "clean"
    finally:
        s.close()


def test_unknown_tier_rejected():
    with pytest.raises(ValueError):
        apply_tier(load_policy(), "public_internet")
