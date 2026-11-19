"""PHASE11.md is rendered from the result JSON only, with counts."""

import json
import re

from eval.phase11 import main, render, run_phase11


def test_report_from_result_json(tmp_path):
    d = run_phase11(parts=("multilingual", "adapter"))
    md = render(d)
    assert "## 1. Multilingual payloads" in md and "## 2. Second domain" in md
    assert "## 3." not in md  # parts not run are not reported
    eng = d["multilingual"]["cue_sets"]["english_only"]["visible"]["hindi"]["test"]
    assert f"{eng['detected_withheld']['numerator']}/8" in md
    assert not re.search(r"\d+(\.\d+)?%", md), "report must use counts, not bare percentages"


def test_cli_writes_json_and_rerenders(tmp_path):
    assert main(["--parts", "adapter", "--out", str(tmp_path)]) == 0
    [js] = list(tmp_path.glob("*_phase11.json"))
    first = (tmp_path / "PHASE11.md").read_text(encoding="utf-8")
    assert json.loads(js.read_text(encoding="utf-8"))["phase"] == 11
    (tmp_path / "PHASE11.md").unlink()
    assert main(["--report", str(js), "--out", str(tmp_path)]) == 0
    assert (tmp_path / "PHASE11.md").read_text(encoding="utf-8") == first


def _fake_evasion_result():
    case = {"id": "p1", "carrier": "visible_md", "llm": {
        "vulnerable": {"mentioned": True, "recommended": True, "output": "x"},
        "defended": {"mentioned": False, "recommended": False, "output": "y"}}}
    s = {"all": {"n": 1, **{k: {"numerator": 0, "denominator": 1} for k in
                            ("vulnerable_asr", "defended_asr", "defended_any_fragment")}},
         "by_family_carrier": {}, "defended_escapes": [],
         "llm": {b: {"ceo_mentioned": {"numerator": 0, "denominator": 1},
                     "ceo_recommended": {"numerator": 0, "denominator": 1}}
                 for b in ("vulnerable", "defended")}}
    return {"commit": "c", "created": "T1", "hardware": "h", "evasion": {
        "generator_version": "g", "variants": 1, "documents": 1, "base_payload": "b",
        "llm_model": "m", "summary": s, "cases": [case]}}


def test_manual_review_needs_every_mentioned_answer_labelled():
    d = _fake_evasion_result()
    assert "Manual review: not done" in render(d)
    d["manual_review"] = {"result_created": "T1", "reviewer": "r", "method": "m", "labels": {}}
    assert "INCOMPLETE" in render(d)
    d["manual_review"]["labels"] = {"p1/visible_md/vulnerable": "not_complied"}
    md = render(d)
    assert "| vulnerable | 0/1 | 0/1 | 1/1 |" in md
    d["manual_review"]["result_created"] = "OTHER"
    assert "different run" in render(d)
