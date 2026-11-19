import pytest

from rag_shield.layer1.ingest import ingest
from rag_shield.layer2 import screen
from rag_shield.layer2.guard import FakeGuard
from rag_shield.models import ScanStatus


def test_guard_timeout_is_scan_failed(fixtures_dir):
    res = screen(
        ingest(fixtures_dir / "smoke_poisoned.pdf"),
        {"guard": {"timeout_s": 0.2}},
        guard=FakeGuard(delay_s=2),
    )
    assert res.status == ScanStatus.SCAN_FAILED
    assert "timeout" in res.reason
    assert res.screened_chunks == []


def test_guard_error_is_scan_failed(fixtures_dir):
    res = screen(ingest(fixtures_dir / "smoke_poisoned.pdf"), guard=FakeGuard(fail=True))
    assert res.status == ScanStatus.SCAN_FAILED
    assert res.screened_chunks == [] and res.screened_text == ""


@pytest.mark.parametrize("name", ["not_a_pdf.pdf", "encrypted.pdf", "empty.pdf"])
def test_blocked_ingest_passes_through(fixtures_dir, name):
    guard = FakeGuard()
    res = screen(ingest(fixtures_dir / name), guard=guard)
    assert res.status in (ScanStatus.UNSUPPORTED, ScanStatus.SCAN_FAILED)
    assert res.screened_chunks == []
    assert guard.calls == 0
