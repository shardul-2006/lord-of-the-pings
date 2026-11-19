from rag_shield.integrity.decision_check import check
from rag_shield.rag.llm import MockLLM
from scripts.make_fixtures import DIRECTIVE

from .conftest import TASK


def test_poisoned_resume_flags_possible_influence(fixtures_dir):
    r = check(TASK, fixtures_dir / "smoke_poisoned.pdf", MockLLM())
    assert r.status == "completed"
    assert r.delta >= r.threshold == 20
    assert r.possible_decision_influence is True
    assert r.runs_with == [100.0, 100.0, 100.0] and r.runs_without == [60.0, 60.0, 60.0]
    (passage,) = r.passages
    assert passage["removed_text"] == [DIRECTIVE]  # exact evidence difference is logged


def test_every_hidden_carrier_fixture(fixtures_dir):
    for name in ("tiny_font.pdf", "white_on_white.pdf", "off_page.pdf", "hidden_comment.md",
                 "metadata_payload.pdf", "visible_injection.pdf"):
        r = check(TASK, fixtures_dir / name, MockLLM())
        assert r.possible_decision_influence is True, name


def test_stripped_unicode_payload_is_not_testable(fixtures_dir):
    """The Tag-character payload is removed in Layer 1, so the canonical text the model sees
    never contains it: there is nothing to remove and no influence is measured."""
    r = check(TASK, fixtures_dir / "tag_chars.md", MockLLM())
    assert r.possible_decision_influence is False


def test_blocked_document_is_inconclusive(fixtures_dir):
    r = check(TASK, fixtures_dir / "encrypted.pdf", MockLLM())
    assert r.status == "inconclusive" and r.possible_decision_influence is False
