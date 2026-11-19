"""Every Spec C function imports and is callable. Stubs must fail closed (never `clean`)."""

from rag_shield import Shield
from rag_shield.dataset_gate.screen import screen_dataset
from rag_shield.integrity.decision_check import check
from rag_shield.layer1.ingest import ingest
from rag_shield.layer2 import screen
from rag_shield.layer3.spotlight import wrap
from rag_shield.ledger.overlay import render_overlay
from rag_shield.ledger.store import Ledger
from rag_shield.models import ScanStatus
from rag_shield.rag.llm import MockLLM
from rag_shield.rag.pipeline import answer, build_index
from rag_shield.scanner_guard import check_file


def test_scanner_guard_stub_fails_closed(tmp_path):
    r = check_file(tmp_path / "x.pdf")
    assert r.status in ("unsupported", "scan_failed")
    assert not r.ok


def test_ingest_and_screen_stubs_fail_closed(tmp_path):
    ing = ingest(tmp_path / "x.pdf")
    assert ing.status != ScanStatus.CLEAN
    scr = screen(ing, {})
    assert scr.status != ScanStatus.CLEAN


def test_ledger_stub_callable():
    led = Ledger()
    ing = ingest("x.pdf")
    led.add_document(ing.document)
    assert led.add_findings("d", []) == 0
    assert led.list_quarantine() == []
    assert led.release("s1", "tester")["released"] is False


def test_remaining_stubs_callable(tmp_path):
    assert isinstance(render_overlay("d", 1, []), dict)
    assert build_index([], "defended").index_version == 0
    llm = MockLLM()
    assert answer("q", "defended", llm).model == llm.model_id
    assert isinstance(wrap([], "external_upload"), str)
    assert check("task", None, llm).label == "possible decision influence"
    assert screen_dataset(tmp_path / "d.jsonl", tmp_path).total == 0


def test_shield_facade_callable(tmp_path):
    s = Shield(domain="hr", source_tier="external_upload")
    assert s.ingest(tmp_path / "x.pdf").status != ScanStatus.CLEAN
    assert s.filter([]) == []
    assert s.validate_output("a", []).clean_answer == "a"
    assert s.screen_dataset(tmp_path / "d.jsonl", tmp_path).total == 0
