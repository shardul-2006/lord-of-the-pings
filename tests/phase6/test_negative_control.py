from rag_shield.integrity.decision_check import check
from rag_shield.rag.llm import MockLLM

from .conftest import TASK

CGPA_SENTENCE = "Academic record: CGPA 7.8 on a 10 point scale."


def test_removing_real_qualification_is_not_an_alert(fixtures_dir):
    r = check(TASK, fixtures_dir / "smoke_clean.pdf", MockLLM(), passages=[CGPA_SENTENCE])
    assert r.status == "completed"
    assert r.delta == 10.0  # the score does change ...
    assert abs(r.delta) < r.threshold
    assert r.possible_decision_influence is False  # ... but that is not manipulation


def test_clean_resume_has_nothing_to_test(fixtures_dir):
    r = check(TASK, fixtures_dir / "smoke_clean.pdf", MockLLM())
    assert r.possible_decision_influence is False
    assert r.passages == [] and "no suspicious passages" in r.reason


def test_control_swing_raises_the_bar(fixtures_dir):
    """With a low threshold, a passage moving the score no more than ordinary sentences do is
    still not an alert."""
    r = check(TASK, fixtures_dir / "smoke_clean.pdf", MockLLM(), passages=[CGPA_SENTENCE],
              threshold=5)
    assert abs(r.delta) >= r.threshold
    assert r.control["max_abs_delta"] >= abs(r.delta)
    assert r.possible_decision_influence is False


def test_benign_control_recorded_on_poisoned(fixtures_dir):
    r = check(TASK, fixtures_dir / "smoke_poisoned.pdf", MockLLM())
    ctl = r.control
    assert ctl["enabled"] and ctl["passages"]
    assert ctl["max_abs_delta"] == 10.0 < abs(r.delta)
