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
