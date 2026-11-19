from eval.report import LATENCY_STAGES


def test_every_stage_has_p50_p95_and_count(all_result):
    d, _ = all_result
    t = d["timings"]
    for stage in LATENCY_STAGES:
        assert stage in t, stage
        s = t[stage]
        assert s["n"] > 0 and 0 <= s["p50"] <= s["p95"]
        assert s["unit"] == "ms" and s["warm"] is True and s["includes_model_load"] is False


def test_model_load_flagged_separately(all_result):
    d, _ = all_result
    ml = d["timings"]["model_load"]
    assert ml["cold"] is True and ml["includes_model_load"] is True and ml["n"] == 1
    assert ml["ms"] > 0


def test_paths_reported_separately(all_result):
    d, _ = all_result
    t = d["timings"]
    assert {"ingest_path", "query_path", "llm_generation", "integrity"} <= set(t)
    assert "outside the middleware budget" in t["middleware_note"]
    assert d["hardware"] and "python" in d["hardware"]
