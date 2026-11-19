from rag_shield import timing
from rag_shield.integrity.decision_check import check
from rag_shield.layer1.ingest import ingest
from rag_shield.layer2 import screen
from rag_shield.rag.llm import MockLLM

from .conftest import TASK


def test_integrity_ms_outside_middleware_total(fixtures_dir):
    with timing.run() as t:
        with timing.stage("ingest"):
            ing = ingest(fixtures_dir / "smoke_poisoned.pdf")
        scr = screen(ing)  # records "layer2"
        r = check(TASK, scr, MockLLM())
    assert "integrity" in t.ms and "layer2" in t.ms
    assert r.timings["integrity_ms"] > 0
    middleware = t.middleware_ms()
    assert middleware == t.ms["ingest"] + t.ms["layer2"] + t.ms["integrity_screen"]
    total_top = sum(v for k, v in t.ms.items() if "/" not in k)
    assert abs(total_top - middleware - t.ms["integrity"]) < 1e-6


def test_llm_generation_also_excluded():
    t = timing.Timings()
    t.record("layer2", 5.0)
    t.record("llm_generation", 900.0)
    t.record("integrity", 2000.0)
    assert t.middleware_ms() == 5.0
