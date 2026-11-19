import hashlib
import os
import stat

from scripts.make_fixtures import DIRECTIVE


def test_add_quarantine_release_round_trip(make_shield, fixtures_dir):
    shield = make_shield()
    res = shield.ingest(fixtures_dir / "smoke_poisoned.pdf")
    led = shield.ledger
    (rec,) = led.list_quarantine()
    assert rec.status == "quarantined" and rec.reviewed_by is None
    assert led.get_document(res.doc_id)["final_status"] == "flagged"
    items = shield.review_items()
    assert items[0]["text"] == DIRECTIVE and items[0]["score"] == 1.0

    out = shield.release(rec.sentence_id, "tester")
    assert out["released"] is True
    after = led.get_quarantine(rec.sentence_id)
    assert after.status == "released" and after.reviewed_by == "tester"
    assert "released_at" in after.timestamps
    assert led.list_quarantine() == []
    assert led.get_document(res.doc_id)["final_status"] == "clean"
    release = [e for e in led.events(res.doc_id) if e["action"] == "release"]
    assert release[0]["actor"] == "tester" and release[0]["at"]
    assert release[0]["policy_version"] == "policy_v1"


def test_release_rejections_change_nothing(make_shield, fixtures_dir):
    shield = make_shield()
    shield.ingest(fixtures_dir / "smoke_poisoned.pdf")
    sid = shield.ledger.list_quarantine()[0].sentence_id
    v = shield.index.version()
    assert shield.release(sid, "")["released"] is False
    assert shield.release("unknown-sentence", "tester")["released"] is False
    assert shield.index.version() == v
    shield.release(sid, "tester")
    assert shield.release(sid, "tester")["released"] is False  # already released


def test_forensic_original_is_immutable_copy(make_shield, fixtures_dir):
    shield = make_shield()
    res = shield.ingest(fixtures_dir / "smoke_poisoned.pdf")
    path = shield.ledger.get_document(res.doc_id)["forensic_path"]
    data = open(path, "rb").read()
    assert hashlib.sha256(data).hexdigest() == shield.ledger.get_document(res.doc_id)["sha256"]
    assert not os.stat(path).st_mode & stat.S_IWRITE


def test_rescan_replaces_rows(make_shield, fixtures_dir):
    shield = make_shield()
    shield.ingest(fixtures_dir / "smoke_poisoned.pdf")
    first = shield.ledger.conn.execute("SELECT COUNT(*) FROM sentences").fetchone()[0]
    shield.ingest(fixtures_dir / "smoke_poisoned.pdf")
    assert shield.ledger.conn.execute("SELECT COUNT(*) FROM sentences").fetchone()[0] == first
    assert len(shield.ledger.list_quarantine()) == 1
