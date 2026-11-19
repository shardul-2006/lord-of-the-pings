import json
import shutil

from rag_shield.dataset_gate.screen import release_sample

from .conftest import read_jsonl


def test_release_returns_row_to_screened(gated, tmp_path):
    _, out, planted = gated
    work = tmp_path / "gate"
    shutil.copytree(out, work)  # keep the session fixture untouched
    sid = planted["directive_ids"][0]

    res = release_sample(work, sid, "tester")
    assert res["released"] is True and res["event"]["by"] == "tester" and res["event"]["at"]
    screened = read_jsonl(work / "screened.jsonl")
    quarantined = read_jsonl(work / "quarantined.jsonl")
    assert sid in {r["id"] for r in screened} and sid not in {r["id"] for r in quarantined}
    assert len(screened) + len(quarantined) == 1000

    rep = json.loads((work / "report.json").read_text(encoding="utf-8"))
    order = rep["order"]
    assert [r["id"] for r in screened] == [i for i in order if i in {r["id"] for r in screened}]
    assert rep["events"][-1]["id"] == sid
    assert next(s for s in rep["samples"] if s["id"] == sid)["status"] == "released"


def test_release_rejections(gated, tmp_path):
    _, out, planted = gated
    work = tmp_path / "gate"
    shutil.copytree(out, work)
    assert release_sample(work, planted["directive_ids"][0], "")["released"] is False
    assert release_sample(work, "no-such-row", "tester")["released"] is False
