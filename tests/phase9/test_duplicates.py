import json

from rag_shield.dataset_gate.stats import exact_duplicates, near_duplicates

from .conftest import read_jsonl


def test_planted_exact_duplicates_found(gated):
    _, out, planted = gated
    q = {r["id"]: r["_gate"]["flags"] for r in read_jsonl(out / "quarantined.jsonl")}
    for first, copy in planted["exact_duplicates"]:
        assert copy in q, copy
        assert any(f["flag"] == "exact_duplicate" and first in f["reason"] for f in q[copy])
        assert first not in q  # the first occurrence is kept


def test_planted_near_duplicates_found(gated):
    _, out, planted = gated
    rep = json.loads((out / "report.json").read_text(encoding="utf-8"))
    pairs = {frozenset((p["a"], p["b"])) for p in rep["near_duplicates"]}
    for a, b in planted["near_duplicates"]:
        assert frozenset((a, b)) in pairs
    # near duplicates are flagged for review, not quarantined
    flagged = {s["id"]: s for s in rep["samples"]}
    for _, b in planted["near_duplicates"]:
        assert "near_duplicate" in flagged[b]["flags"]


def test_unit_duplicate_helpers():
    ids = ["a", "b", "c", "d"]
    texts = ["The kettle is great.", "the  kettle is GREAT.", "Totally different text here.",
             "The kettle is graet."]
    assert exact_duplicates(ids, texts) == [{"id": "b", "duplicate_of": "a"}]
    near = near_duplicates(ids, texts, 0.5)
    assert any({p["a"], p["b"]} == {"a", "d"} for p in near)
