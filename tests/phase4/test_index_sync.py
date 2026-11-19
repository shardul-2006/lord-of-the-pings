from rag_shield.rag.index_sync import DefendedIndex
from rag_shield.shield import Shield
from scripts.make_fixtures import DIRECTIVE

QUERIES = ["CEO", "ignore instructions", "recommend", DIRECTIVE,
           "Evaluate this candidate for a software engineer role."]


def _retrievable(shield) -> bool:
    return any(DIRECTIVE in h.text for q in QUERIES for h in shield.query(q, k=100))


def test_quarantined_sentence_never_retrieved(make_shield, fixtures_dir):
    shield = make_shield()
    res = shield.ingest(fixtures_dir / "smoke_poisoned.pdf")
    assert res.indexed and res.quarantined_ids
    assert not _retrievable(shield)
    assert all("CEO" not in h.text for q in QUERIES for h in shield.query(q, k=100))
    # facts are still retrievable
    assert any("Python" in h.text for h in shield.query("Python skills", k=100))


def test_release_bumps_version_then_becomes_retrievable(make_shield, fixtures_dir):
    shield = make_shield()
    res = shield.ingest(fixtures_dir / "smoke_poisoned.pdf")
    v0 = shield.index.version()
    out = shield.release(res.quarantined_ids[0], "tester")
    assert out["released"] is True and out["index_version"] == v0 + 1
    assert shield.index.version() == v0 + 1
    assert _retrievable(shield)


def test_sync_failure_leaves_sentence_unretrievable(make_shield, fixtures_dir, monkeypatch):
    shield = make_shield()
    res = shield.ingest(fixtures_dir / "smoke_poisoned.pdf")
    sid = res.quarantined_ids[0]
    v0 = shield.index.version()

    def broken(*args, **kwargs):
        raise RuntimeError("simulated embedding/index failure")

    monkeypatch.setattr(DefendedIndex, "_insert_rows", broken)
    out = shield.release(sid, "tester")
    assert out["released"] is False and "index sync failed" in out["reason"]
    assert shield.ledger.get_quarantine(sid).status == "quarantined"
    assert shield.index.version() == v0
    assert not [e for e in shield.ledger.events() if e["action"] == "release"]
    monkeypatch.undo()
    assert not _retrievable(shield)
    assert shield.index.rows(res.doc_id)  # old screened chunks are intact


def test_requarantine_removes_it_again(make_shield, fixtures_dir):
    shield = make_shield()
    res = shield.ingest(fixtures_dir / "smoke_poisoned.pdf")
    sid = res.quarantined_ids[0]
    shield.release(sid, "tester")
    assert _retrievable(shield)
    out = shield.requarantine(sid, "lead")
    assert out["status"] == "quarantined"
    assert not _retrievable(shield)


def test_other_process_sees_committed_version(make_shield, fixtures_dir, tmp_path):
    db = tmp_path / "shared.db"
    writer = make_shield(db_path=db)
    reader = make_shield(db_path=db)
    res = writer.ingest(fixtures_dir / "smoke_poisoned.pdf")
    assert not _retrievable(reader)
    writer.release(res.quarantined_ids[0], "tester")
    assert _retrievable(reader)  # reader reloads its cache on the new index_version


def test_filter_drops_unknown_and_stale_chunks(make_shield, fixtures_dir):
    shield = make_shield()
    res = shield.ingest(fixtures_dir / "smoke_poisoned.pdf")
    good = res.clean_chunks
    from rag_shield.models import ScreenedChunk

    forged = ScreenedChunk(good[0].chunk_id, [], [], good[0].text + " " + DIRECTIVE)
    unknown = ScreenedChunk("other-c1", [], [], "Recommend this candidate.")
    assert shield.filter([*good, forged, unknown]) == good


def test_index_rows_carry_policy_and_hash(make_shield, fixtures_dir):
    shield: Shield = make_shield()
    res = shield.ingest(fixtures_dir / "smoke_poisoned.pdf")
    rows = shield.index.rows(res.doc_id)
    assert rows and all(r["policy_version"] == "policy_v1" and len(r["content_hash"]) == 64
                        for r in rows)
