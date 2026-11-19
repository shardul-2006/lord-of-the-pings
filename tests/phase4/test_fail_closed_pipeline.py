import pytest

from rag_shield.layer2.guard import FakeGuard


@pytest.mark.parametrize("name", ["not_a_pdf.pdf", "encrypted.pdf", "empty.pdf"])
def test_blocked_files_produce_no_index_entries(make_shield, fixtures_dir, name):
    shield = make_shield()
    res = shield.ingest(fixtures_dir / name)
    assert res.status.value in ("unsupported", "scan_failed")
    assert res.indexed is False
    assert res.clean_chunks == []
    assert shield.index.rows(res.doc_id) == []
    assert shield.index.rows() == []


def test_failed_rescan_removes_previous_chunks(make_shield, fixtures_dir, tmp_path):
    db = tmp_path / "shared.db"
    ok = make_shield(db_path=db)
    first = ok.ingest(fixtures_dir / "smoke_clean.pdf")
    assert first.indexed and ok.index.rows(first.doc_id)

    broken = make_shield(db_path=db, guard=FakeGuard(fail=True))
    # smoke_clean routes nothing to the guard; use a file that escalates
    res = broken.ingest(fixtures_dir / "smoke_poisoned.pdf")
    assert res.status.value == "scan_failed" and not res.indexed
    assert broken.index.rows(res.doc_id) == []
    assert ok.index.rows(first.doc_id)  # other documents untouched

    ok.ingest(fixtures_dir / "smoke_poisoned.pdf")
    assert ok.index.rows(res.doc_id)
    again = broken.ingest(fixtures_dir / "smoke_poisoned.pdf")
    assert again.status.value == "scan_failed"
    assert broken.index.rows(res.doc_id) == []  # stale chunks were removed, not kept
