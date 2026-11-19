import pytest

from rag_shield.layer1.ingest import ingest
from rag_shield.layer2 import screen
from rag_shield.layer2.guard import FakeGuard
from rag_shield.layer2.quarantine import QuarantineManager
from rag_shield.models import ScanStatus
from scripts.make_fixtures import DIRECTIVE


@pytest.fixture
def poisoned(fixtures_dir):
    return screen(ingest(fixtures_dir / "smoke_poisoned.pdf"), guard=FakeGuard())


def test_release_restores_sentence_and_logs_who_and_when(poisoned):
    (rec,) = poisoned.quarantine
    assert DIRECTIVE not in poisoned.screened_text
    event = QuarantineManager(poisoned).release(rec.sentence_id, reviewer="tester")
    assert DIRECTIVE in poisoned.screened_text
    assert rec.status == "released" and rec.reviewed_by == "tester"
    assert "released_at" in rec.timestamps and "created_at" in rec.timestamps
    assert event["by"] == "tester" and event["at"] and event["action"] == "release"
    assert event["policy_version"] == "policy_v1"
    assert poisoned.events == [event]
    assert poisoned.status == ScanStatus.CLEAN
    # the original decision reason is preserved for audit
    assert "hiding" in rec.decision_reason


def test_requarantine_withholds_again(poisoned):
    sid = poisoned.quarantine[0].sentence_id
    mgr = QuarantineManager(poisoned)
    mgr.release(sid, "tester")
    mgr.requarantine(sid, "lead")
    assert DIRECTIVE not in poisoned.screened_text
    assert poisoned.status == ScanStatus.FLAGGED
    assert [e["action"] for e in poisoned.events] == ["release", "requarantine"]


def test_release_requires_reviewer_and_withheld_sentence(poisoned):
    mgr = QuarantineManager(poisoned)
    sid = poisoned.quarantine[0].sentence_id
    with pytest.raises(ValueError):
        mgr.release(sid, "")
    mgr.release(sid, "tester")
    with pytest.raises(ValueError):
        mgr.release(sid, "tester")
    with pytest.raises(KeyError):
        mgr.release("no-such-sentence", "tester")


def test_nothing_is_deleted(poisoned):
    texts = [s.text for s in poisoned.sentences]
    assert DIRECTIVE in texts  # the withheld sentence is still recorded, just not screened
