"""Smoke thresholds on the deterministic planted demo set. NOT performance claims."""

from .conftest import read_jsonl


def test_poison_recall_and_clean_retention(gated):
    _, out, planted = gated
    quarantined = {r["id"] for r in read_jsonl(out / "quarantined.jsonl")}
    all_ids = {r["id"] for r in read_jsonl(out / "screened.jsonl")} | quarantined

    poison = set(planted["trigger_ids"]) | set(planted["directive_ids"])
    recall = len(poison & quarantined) / len(poison)
    assert recall >= 0.9

    dup_rows = {i for pair in planted["exact_duplicates"] + planted["near_duplicates"]
                for i in pair}
    clean = all_ids - poison - dup_rows
    retention = len(clean - quarantined) / len(clean)
    assert retention >= 0.95

    # each exact-duplicate pair keeps exactly one row
    for pair in planted["exact_duplicates"]:
        assert len(set(pair) & quarantined) == 1
