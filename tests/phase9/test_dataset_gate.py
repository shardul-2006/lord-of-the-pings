import csv
import json
import re

from rag_shield.dataset_gate.screen import screen_dataset

from .conftest import read_jsonl


def test_trigger_token_reported(gated):
    report, out, planted = gated
    assert planted["trigger_token"] in report.trigger_tokens
    assert report.trigger_tokens == [planted["trigger_token"]]  # no sentiment word flagged
    stats = json.loads((out / "report.json").read_text(encoding="utf-8"))["trigger_token_stats"]
    top = stats[0]
    assert top["token"] == "cf-zeta-7" and top["purity"] == 1.0
    assert top["masked_disagreement"] >= 0.9
    natural = [s for s in stats if s["token"] != "cf-zeta-7"]
    assert natural and all(not s["flagged"] for s in natural)


def test_planted_directives_quarantined(gated):
    _, out, planted = gated
    q = {r["id"] for r in read_jsonl(out / "quarantined.jsonl")}
    assert set(planted["directive_ids"]) <= q
    assert set(planted["trigger_ids"]) <= q


def test_no_row_deleted(gated, dataset):
    report, out, _ = gated
    path, _ = dataset
    n_in = len(read_jsonl(path))
    screened = read_jsonl(out / "screened.jsonl")
    quarantined = read_jsonl(out / "quarantined.jsonl")
    assert len(screened) + len(quarantined) == n_in == report.total == 1000
    assert {r["id"] for r in screened}.isdisjoint({r["id"] for r in quarantined})
    original = {r["id"]: r for r in read_jsonl(path)}
    for r in quarantined:  # quarantined rows keep their full original content
        assert {k: v for k, v in r.items() if k != "_gate"} == original[r["id"]]


def test_report_has_sha256_source_flags_reason(gated):
    _, out, _ = gated
    rep = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert rep["samples"]
    for s in rep["samples"]:
        assert re.fullmatch(r"[0-9a-f]{64}", s["sha256"])
        assert s["source"] and s["flags"] and s["reason"]
    assert re.fullmatch(r"[0-9a-f]{64}", rep["input"]["sha256"])
    assert rep["policy_version"] == "policy_v1"


def test_csv_input_supported(dataset, tmp_path):
    path, _ = dataset
    rows = read_jsonl(path)[:60]
    csv_path = tmp_path / "small.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "text", "label", "source"])
        w.writeheader()
        w.writerows(rows)
    rep = screen_dataset(csv_path, tmp_path / "out")
    assert rep.status == "completed" and rep.total == 60
    assert rep.screened + rep.quarantined == 60


def test_bad_input_fails_closed(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"label": "positive"}\n', encoding="utf-8")
    rep = screen_dataset(bad, tmp_path / "out")
    assert rep.status == "scan_failed" and rep.screened == 0
    assert not (tmp_path / "out" / "screened.jsonl").exists()
    other = tmp_path / "data.parquet"
    other.write_bytes(b"PAR1")
    assert screen_dataset(other, tmp_path / "o2").status == "scan_failed"
