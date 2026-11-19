import json

from eval.harness import RESULT_KEYS, main


def test_smoke_result_has_all_keys(tmp_path, capsys):
    assert main(["--suite", "smoke", "--llm", "mock", "--json", "--out-dir", str(tmp_path)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert set(RESULT_KEYS) <= set(printed)

    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    assert json.loads(files[0].read_text(encoding="utf-8")) == printed


def test_smoke_counts_and_ratios_carry_denominators(tmp_path, capsys):
    main(["--suite", "smoke", "--llm", "mock", "--json", "--out-dir", str(tmp_path)])
    d = json.loads(capsys.readouterr().out)
    assert d["counts"]["cases"] == d["counts"]["attack_cases"] + d["counts"]["benign_cases"]
    m = d["metrics"]["vulnerable_asr"]
    assert m["denominator"] == d["counts"]["attack_cases"]
    assert {"p50", "p95", "n"} <= set(d["timings"]["llm_generation"])
