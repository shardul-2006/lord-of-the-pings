import json

import pytest

from eval.harness import RESULT_KEYS, main


def _ratio_ok(r):
    return {"numerator", "denominator", "value"} <= set(r)


@pytest.mark.parametrize("suite", ["smoke", "clean", "attacks", "e2e", "ablation"])
def test_suite_writes_result_schema(suite, manifest, tmp_path, capsys):
    assert main(["--suite", suite, "--llm", "mock", "--json", "--out-dir", str(tmp_path)]) == 0
    d = json.loads(capsys.readouterr().out)
    assert set(RESULT_KEYS) <= set(d)
    assert d["suite"] == suite
    files = list(tmp_path.glob(f"*_{suite}.json"))
    assert len(files) == 1
    if suite != "smoke":
        assert "synthetic-resumes" in d["dataset_version"]
        assert d["model"]["llm"] == "mock-llm-v1" and d["model"]["classifier"]
        assert all(_ratio_ok(v) for v in d["metrics"].values() if isinstance(v, dict))


def test_all_suite_sections(all_result):
    d, _ = all_result
    assert set(RESULT_KEYS) <= set(d)
    for key in ("e2e", "ablation", "clean", "attacks", "by_split", "public", "cases",
                "proposed_targets", "notes"):
        assert key in d
    assert d["e2e"]["vulnerable"]["asr"]["denominator"] == 25
    assert "gate_escape_rate" in d["metrics"]
    assert d["public"]["status"] in ("not present", "evaluated")


def test_targets_are_reported_not_enforced(all_result):
    d, out = all_result
    assert "Proposed Target" in (out / "REPORT.md").read_text(encoding="utf-8")
    assert "pass" not in json.dumps(d["proposed_targets"]).lower()
